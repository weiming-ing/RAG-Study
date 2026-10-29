import asyncio
import json
import os
import httpx
from typing import List, Optional

from config import (
    CHROMA_DIR,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_DEVICE,
    TOP_K,
    SIMILARITY_THRESHOLD,
    USE_HYBRID_SEARCH,
    VECTOR_WEIGHT,
    BM25_WEIGHT,
    JAVA_BACKEND_URL,
)
from utils.internal_api import internal_headers
from utils.runtime_config import get_config_int

JAVA_TIMEOUT = 15.0


class RAGService:
    """
    RAG 核心检索服务

    核心职责：统一的检索入口，优先级为 Java 后端 > 本地 ChromaDB 降级。

    检索管线：
      1. 查询到达 → _check_java_backend() 检测 Java 后端健康状态
      2. 如果 Java 可用 → _java_search() 调用 Java 混合检索（向量 + BM25）
      3. 如果 Java 不可用 → _local_search() 降级到本地 ChromaDB 向量检索
      4. build_context() 将检索结果拼接为 LLM prompt 上下文

    依赖：
      - Java 后端 HybridSearchService（/api/internal/search）
      - 本地 ChromaDB + sentence-transformers（降级方案）
    """

    def __init__(self):
        self._java_available = None

    async def _check_java_backend(self) -> bool:
        """检测 Java 后端是否可用（缓存结果，避免重复请求）"""
        if self._java_available is not None:
            return self._java_available
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(
                    f"{JAVA_BACKEND_URL}/api/internal/health",
                    headers=internal_headers(),
                )
                self._java_available = resp.status_code == 200
        except Exception:
            self._java_available = False
        return self._java_available

    async def _java_search(
        self, query: str, top_k: int, use_hybrid: bool, threshold: float,
        kb_id: str = None, kb_ids: list = None
    ) -> List[dict]:
        """调用 Java 后端混合检索接口，过滤低于阈值的低分结果。

        kb_id: 可选，指定知识库 ID 用于过滤（按 kbId payload 字段精确匹配）
        kb_ids: 可选，多知识库范围（filters["kbIds"]="1,2,3"），授权强制依据
        """
        try:
            filters = {}
            if kb_ids:
                filters["kbIds"] = ",".join(str(int(k)) for k in kb_ids)
            elif kb_id:
                filters["kbId"] = str(kb_id)

            async with httpx.AsyncClient(timeout=JAVA_TIMEOUT) as client:
                req_body = {
                    "query": query,
                    "topK": top_k,
                    "enableHybrid": use_hybrid,
                    "filters": filters,
                }
                if kb_ids:
                    req_body["kbIds"] = [int(k) for k in kb_ids]
                elif kb_id:
                    req_body["kbId"] = int(kb_id)
                resp = await client.post(
                    f"{JAVA_BACKEND_URL}/api/internal/search",
                    headers=internal_headers(),
                    json=req_body,
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                if data.get("code") != 0:
                    return []

                search_data = data.get("data", {})
                results = search_data.get("results", [])

                sources = []
                for r in results:
                    score = r.get("score", 0)
                    if score < threshold:
                        continue
                    metadata = r.get("metadata", {})

                    chunk_id = r.get("chunkId", metadata.get("chunkId", ""))
                    doc_id = metadata.get("documentId", "")
                    doc_name = metadata.get("docName", metadata.get("filename", "未知文档"))
                    chunk_index = metadata.get("chunkIndex", metadata.get("parentChunkIndex", 0))
                    parent_content = r.get("parentContent", "")
                    parent_chunk_id = r.get("parentChunkId", metadata.get("parentChunkId", ""))

                    sources.append({
                        "content": parent_content if parent_content else r.get("content", ""),
                        "filename": doc_name,
                        "page": chunk_index,
                        "score": round(score, 4),
                        "doc_id": doc_id,
                        "chunk_id": chunk_id,
                        "chunk_index": chunk_index,
                        "parent_chunk_id": parent_chunk_id,
                        "kb_id": metadata.get("kbId", ""),
                    })
                return sources
        except Exception:
            return []

    def _local_search(
        self, query: str, top_k: int, threshold: float,
        kb_id: str = None, kb_ids: list = None,
    ) -> List[dict]:
        """本地 ChromaDB 降级检索（依赖为可选组件，见 requirements-fallback.txt）。

        容器部署下 Java 引擎是 compose 兄弟服务，本路径通常不可用；因此缺少
        可选依赖或本地模型时只记录日志并返回空结果，不影响主链路。

        kb_id/kb_ids 语义与 _java_search 一致：降级路径同样强制 KB 范围，
        按 metadata.kb_id 过滤；本地库无该元数据时查空——fail closed。
        """
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            print(f"[RAG] 本地降级检索不可用（缺少可选依赖 {exc.name}）。"
                  f"如需启用请安装 backend/requirements-fallback.txt")
            return []

        try:
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            collection = client.get_collection("knowledge_base")

            model = SentenceTransformer(
                EMBEDDING_MODEL_NAME,
                device=EMBEDDING_DEVICE,
                local_files_only=True,
            )
            query_embedding = model.encode(query, normalize_embeddings=True).tolist()

            where = None
            if kb_ids:
                where = {"kb_id": {"$in": [str(int(k)) for k in kb_ids]}}
            elif kb_id:
                where = {"kb_id": str(kb_id)}

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k * 2,
                include=["documents", "metadatas", "distances"],
                where=where,
            )
        except Exception as exc:
            print(f"[RAG] 本地降级检索失败，已跳过: {type(exc).__name__}: {exc}")
            return []

        if not results["ids"] or not results["ids"][0]:
            return []

        sources = []
        for i in range(len(results["ids"][0])):
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 1.0
            similarity = 1.0 - distance

            if similarity < threshold:
                continue

            sources.append({
                "content": results["documents"][0][i] if results["documents"] else "",
                "filename": metadata.get("filename", metadata.get("source", "未知文档")),
                "page": metadata.get("page", metadata.get("chunk_index", 0)),
                "score": round(similarity, 4),
                "doc_id": metadata.get("doc_id", ""),
                "chunk_index": metadata.get("chunk_index", i),
                "kb_id": metadata.get("kb_id", ""),
            })

            if len(sources) >= top_k:
                break

        return sources

    def build_context(self, sources: List[dict]) -> str:
        """将检索结果拼接为 LLM 上下文：按 [来源N] 格式组织，标注文档名和相关度"""
        if not sources:
            return ""

        lines = []
        for i, src in enumerate(sources, 1):
            filename = src.get("filename", "未知")
            score = src.get("final_score", src.get("score", 0))
            lines.append(f"[来源 {i}] {filename} (相关度: {score:.2f})")
            lines.append(src.get("content", ""))
            lines.append("")

        return "\n".join(lines)

    async def retrieve(
        self,
        query: str,
        top_k: int = None,
        use_hybrid: bool = None,
        threshold: float = None,
        kb_id: str = None,
        kb_ids: list = None,
    ) -> List[dict]:
        """统一检索入口：优先 Java 后端 → 降级本地 ChromaDB

        kb_id: 可选，单知识库过滤（兼容旧调用）
        kb_ids: 可选，多知识库范围——服务端授权解析结果（kb_access 服务），
                三级可见级别的强制依据；与 kb_id 同时给出时以 kb_ids 为准
        """
        if top_k is None:
            # top_k 消费管理台"系统配置"的 rag.default_top_k（60s 缓存），
            # KB 级 topK 由调用方显式传入时不受影响
            top_k = await get_config_int("rag.default_top_k", TOP_K)
        if use_hybrid is None:
            use_hybrid = USE_HYBRID_SEARCH
        if threshold is None:
            threshold = SIMILARITY_THRESHOLD

        if await self._check_java_backend():
            return await self._java_search(query, top_k, use_hybrid, threshold, kb_id, kb_ids)

        return await asyncio.to_thread(self._local_search, query, top_k, threshold, kb_id, kb_ids)

    async def multi_hop_retrieve(
        self,
        original_query: str,
        optimized_query: str,
        initial_sources: List[dict],
        kb_id: str = None,
    ) -> List[dict]:
        return initial_sources


rag_service = RAGService()