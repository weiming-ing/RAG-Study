"""
重排序服务（已迁移至 Java 后端）

原因：重排序功能需要向量计算能力，已统一迁移至 Java 后端 RerankerService.java。
Java 后端通过 /api/internal/search/rerank 接口提供重排序检索服务，
Python 前端通过 http_client 调用 Java 后端 API 获取重排序结果。

原始实现基于 sentence-transformers CrossEncoder，现保留注释供参考。
"""

# 重排序功能已迁移至 Java 后端 (RerankerService.java)
# Java 后端通过 /api/internal/search/rerank 接口提供重排序检索服务
# Python 前端通过 http_client 调用 Java 后端 API 获取重排序结果

# from typing import List, Dict, Optional
# from sentence_transformers import CrossEncoder
# 
# 
# class RerankerService:
#     ...
# 
# reranker_service = RerankerService()