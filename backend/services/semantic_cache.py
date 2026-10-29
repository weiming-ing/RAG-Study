"""
语义缓存服务（Semantic Cache）

核心职责：对用户提问做向量化后，在 Redis 缓存中查找语义相似的历史提问。
命中则直接返回缓存的答案和检索结果，跳过完整的 RAG 检索 + LLM 生成流程。

缓存策略：
  1. 每个问题用 Java 后端计算 512 维语义向量
  2. 与 Redis 中同一知识库范围内已有的缓存向量做余弦相似度匹配
  3. 相似度 >= 阈值（0.92）则命中，直接返回
  4. 未命中 → 正常 RAG 流程 → 异步写入缓存

权限边界：缓存按知识库（kb_id）隔离——不同 KB 的条目互不命中，
防止无权限用户通过相似提问读到其他 KB 的缓存答案。

性能收益：
  - 命中时延迟从 ~960ms 降到 ~50ms（仅向量化 + Redis 查询）
  - FAQ 类高频问题缓存命中率预期 30-50%

存储设计（Redis，{scope} 为 kb_id 或 "all"）：
  Key:   sc:v:{scope}:{uuid}        → 向量（512个float的JSON）
  Key:   sc:a:{scope}:{uuid}        → 答案文本
  Key:   sc:s:{scope}:{uuid}        → 检索来源 JSON
  Key:   sc:q:{scope}:{uuid}        → 原始问题文本
  Key:   sc:idx:{scope}:{text_hash} → uuid（MD5索引，用于精确去重）

依赖：
  - Java 后端 /api/internal/search/embed（获取向量）
  - Redis（向量存储 + 近似检索）
"""

import hashlib
import json
import math
import time
import uuid
from typing import Optional, List

import httpx

from config import JAVA_BACKEND_URL, SEMANTIC_CACHE_ENABLED, SEMANTIC_CACHE_THRESHOLD, SEMANTIC_CACHE_TTL
from database.db import get_redis
from utils.internal_api import internal_headers

SEMANTIC_THRESHOLD = SEMANTIC_CACHE_THRESHOLD
CACHE_TTL_SECONDS = SEMANTIC_CACHE_TTL
MAX_CACHE_ENTRIES = 200
VECTOR_DIM = 512

JAVA_EMBED_URL = f"{JAVA_BACKEND_URL}/api/internal/search/embed"
JAVA_TIMEOUT = 10.0


def _scope(kb_id: Optional[str]) -> str:
    """缓存条目的隔离范围：指定知识库用其 kb_id，未指定用 all"""
    return str(kb_id) if kb_id else "all"


class SemanticCacheService:
    """
    语义缓存服务

    使用方式：
        cache = SemanticCacheService()
        hit = await cache.lookup(question, kb_id=kb_id)
        if hit:
            return hit["answer"], hit["sources"]  # 直接返回
        else:
            answer, sources = normal_rag_flow(question)
            await cache.store(question, answer, sources, kb_id=kb_id)
    """

    def __init__(self):
        self._stats = {"hits": 0, "misses": 0, "total_lookup_ms": 0}

    def stats(self) -> dict:
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0
        return {**self._stats, "total": total, "hit_rate": round(hit_rate, 3)}

    async def _get_vector(self, text: str) -> Optional[List[float]]:
        """调用 Java 后端获取文本向量"""
        try:
            async with httpx.AsyncClient(timeout=JAVA_TIMEOUT) as client:
                resp = await client.post(
                    JAVA_EMBED_URL,
                    headers=internal_headers(),
                    json={"text": text},
                )
                if resp.status_code != 200:
                    return None
                data = resp.json()
                if data.get("code") != 0:
                    return None
                return data["data"]["vector"]
        except Exception:
            return None

    def _text_hash(self, text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """余弦相似度：a·b / (|a| * |b|)"""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def _scan_ids(self, r, prefix: str) -> List[str]:
        """SCAN 遍历指定前缀下的向量 key，返回条目 id 列表。

        使用 SCAN 而非 KEYS：KEYS 是 O(N) 阻塞命令，会卡住整个 Redis。
        """
        ids = []
        async for key in r.scan_iter(match=f"{prefix}*", count=100):
            # key 形如 sc:v:{scope}:{id}，取最后一段作为条目 id
            parts = key.split(":")
            if len(parts) >= 4:
                ids.append(parts[-1])
        return ids

    async def lookup(self, question: str, kb_id: Optional[str] = None) -> Optional[dict]:
        """
        语义缓存查找：返回命中的缓存结果或 None（只在 kb_id 范围内匹配）

        Returns:
            dict with keys: answer, sources, similarity
            或 None 表示未命中
        """
        if not SEMANTIC_CACHE_ENABLED:
            return None

        t0 = time.time()
        scope = _scope(kb_id)

        query_vector = await self._get_vector(question)
        if query_vector is None:
            self._stats["misses"] += 1
            return None

        try:
            r = await get_redis()
            entry_ids = await self._scan_ids(r, f"sc:v:{scope}:")
            if not entry_ids:
                self._stats["misses"] += 1
                return None

            best_similarity = -1.0
            best_id = None

            for entry_id in entry_ids:
                cached_str = await r.get(f"sc:v:{scope}:{entry_id}")
                if not cached_str:
                    continue
                try:
                    cached_vector = json.loads(cached_str)
                except json.JSONDecodeError:
                    continue
                if len(cached_vector) != VECTOR_DIM:
                    continue
                sim = self._cosine_similarity(query_vector, cached_vector)
                if sim > best_similarity:
                    best_similarity = sim
                    best_id = entry_id

            if best_similarity >= SEMANTIC_THRESHOLD and best_id:
                answer = await r.get(f"sc:a:{scope}:{best_id}")
                sources_str = await r.get(f"sc:s:{scope}:{best_id}")
                if answer:
                    sources = json.loads(sources_str) if sources_str else []
                    self._stats["hits"] += 1
                    self._stats["total_lookup_ms"] += (time.time() - t0) * 1000
                    return {
                        "answer": answer,
                        "sources": sources,
                        "similarity": round(best_similarity, 4),
                    }

        except Exception:
            pass

        self._stats["misses"] += 1
        return None

    async def store(self, question: str, answer: str, sources: List[dict], kb_id: Optional[str] = None):
        """
        将 RAG 结果写入语义缓存（写入 kb_id 对应的隔离范围）

        缓存结构（{scope} 为 kb_id 或 "all"）：
          sc:v:{scope}:{id}  → 向量 JSON
          sc:a:{scope}:{id}  → 答案文本
          sc:s:{scope}:{id}  → 来源 JSON
          sc:q:{scope}:{id}  → 原始问题
          sc:idx:{scope}:{md5} → id（精确去重索引）
        """
        if not SEMANTIC_CACHE_ENABLED:
            return
        scope = _scope(kb_id)
        try:
            query_vector = await self._get_vector(question)
            if query_vector is None:
                return

            entry_id = str(uuid.uuid4())[:12]
            text_hash = self._text_hash(question)

            r = await get_redis()

            existing_id = await r.get(f"sc:idx:{scope}:{text_hash}")
            if existing_id:
                return

            pipe = r.pipeline()
            pipe.setex(f"sc:v:{scope}:{entry_id}", CACHE_TTL_SECONDS, json.dumps(query_vector))
            pipe.setex(f"sc:a:{scope}:{entry_id}", CACHE_TTL_SECONDS, answer)
            pipe.setex(f"sc:s:{scope}:{entry_id}", CACHE_TTL_SECONDS, json.dumps(sources, ensure_ascii=False))
            pipe.setex(f"sc:q:{scope}:{entry_id}", CACHE_TTL_SECONDS, question)
            pipe.setex(f"sc:idx:{scope}:{text_hash}", CACHE_TTL_SECONDS, entry_id)
            await pipe.execute()

            await self._evict_overflow(r, scope)

        except Exception:
            pass

    async def _evict_overflow(self, r, scope: str):
        """超出容量上限时，按剩余 TTL 升序淘汰最旧的条目（含 idx 索引）"""
        entry_ids = await self._scan_ids(r, f"sc:v:{scope}:")
        if len(entry_ids) <= MAX_CACHE_ENTRIES:
            return

        # 先取回所有 TTL 再排序：不能把协程对象当排序键（原实现对 r.ttl 未 await，恒为 0）
        ttl_pairs = []
        for entry_id in entry_ids:
            ttl = await r.ttl(f"sc:v:{scope}:{entry_id}")
            ttl_pairs.append((entry_id, ttl))

        # TTL 小的先淘汰（-1 表示无过期，最后淘汰）
        ttl_pairs.sort(key=lambda pair: pair[1])
        for entry_id, _ in ttl_pairs[:max(0, len(ttl_pairs) - MAX_CACHE_ENTRIES)]:
            question = await r.get(f"sc:q:{scope}:{entry_id}")
            pipe = r.pipeline()
            pipe.delete(f"sc:v:{scope}:{entry_id}")
            pipe.delete(f"sc:a:{scope}:{entry_id}")
            pipe.delete(f"sc:s:{scope}:{entry_id}")
            pipe.delete(f"sc:q:{scope}:{entry_id}")
            if question:
                pipe.delete(f"sc:idx:{scope}:{self._text_hash(question)}")
            await pipe.execute()

    async def clear(self):
        """清空所有缓存"""
        try:
            r = await get_redis()
            keys = [key async for key in r.scan_iter(match="sc:*", count=200)]
            if keys:
                await r.delete(*keys)
        except Exception:
            pass


semantic_cache = SemanticCacheService()
