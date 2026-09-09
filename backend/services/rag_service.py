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
)

JAVA_BACKEND_URL = "http://localhost:8002"
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
                resp = await client.get(f"{JAVA_BACKEND_URL}/api/internal/health")
                self._java_available = resp.status_code == 200
        except Exception:
            self._java_available = False
        return self._java_available

    async def _java_search(
        self, query: str, top_k: int, use_hybrid: bool, threshold: float
    ) -> List[dict]:
        """调用 Java 后端混合检索接口，过滤低于阈值的低分结果"""
        try:
            async with httpx.AsyncClient(timeout=JAVA_TIMEOUT) as client:
                resp = await client.post(
                    f"{JAVA_BACKEND_URL}/api/internal/search",
                    json={
                        "query": query,
                        "topK": top_k,
                        "enableHybrid": use_hybrid,
                        "filters": {},
                    },
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                if not data.get("success"):
                    return []

                search_data = data.get("data", {})
                results = search_data.get("results", [])

                sources = []
                for r in results:
                    score = r.get("score", 0)
                    if score < threshold:
                        continue
                    metadata = r.get("metadata", {})
                    sources.append({
                        "content": r.get("content", ""),
                        "filename": metadata.get("docName", metadata.get("filename", "未知文档")),
                        "page": metadata.get("chunkIndex", metadata.get("parentChunkIndex", 0)),
                        "score": round(score, 4),
                        "doc_id": metadata.get("documentId", r.get("id", "")),
                        "chunk_index": metadata.get("chunkIndex", metadata.get("parentChunkIndex", 0)),
                        "chunk_id": r.get("chunkId", metadata.get("chunkId", "")),
                    })
                return sources
        except Exception:
            return []

    def _local_search(
        self, query: str, top_k: int, threshold: float
    ) -> List[dict]:
        """本地 ChromaDB 降级检索：使用 sentence-transformers 向量化后做余弦相似度查询"""
        import chromadb
        from sentence_transformers import SentenceTransformer

        try:
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            collection = client.get_collection("knowledge_base")
        except Exception:
            return []

        model = SentenceTransformer(
            EMBEDDING_MODEL_NAME,
            device=EMBEDDING_DEVICE,
            local_files_only=True,
        )
        query_embedding = model.encode(query, normalize_embeddings=True).tolist()

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k * 2,
            include=["documents", "metadatas", "distances"],
        )

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
    ) -> List[dict]:
        """统一检索入口：优先 Java 后端 → 降级本地 ChromaDB"""
        if top_k is None:
            top_k = TOP_K
        if use_hybrid is None:
            use_hybrid = USE_HYBRID_SEARCH
        if threshold is None:
            threshold = SIMILARITY_THRESHOLD

        if await self._check_java_backend():
            sources = await self._java_search(query, top_k, use_hybrid, threshold)
            if sources:
                return sources

        return self._local_search(query, top_k, threshold)

    async def multi_hop_retrieve(
        self,
        original_query: str,
        optimized_query: str,
        initial_sources: List[dict],
    ) -> List[dict]:
        return initial_sources


rag_service = RAGService()