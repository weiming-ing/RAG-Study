"""
BM25 稀疏检索服务（已迁移至 Java 后端）

原因：BM25 全文检索需要 Lucene 索引引擎，已统一迁移至 Java 后端 Bm25ServiceImpl.java。
Java 后端使用 Lucene + SmartChineseAnalyzer 实现 BM25 索引，通过 /api/internal/search 接口提供检索服务。
Python 前端通过 rag_service._java_search() 调用 Java 后端 API 获取混合检索结果。

原始实现基于 rank_bm25 库（BM25Okapi），现保留注释供参考。
"""

# BM25 稀疏检索已迁移至 Java 后端 (Bm25ServiceImpl.java)
# Java 后端使用 Lucene 实现 BM25 索引，通过 /api/internal/search 接口提供检索服务
# Python 前端通过 http_client 调用 Java 后端 API 获取检索结果

# import pickle
# import re
# from pathlib import Path
# from typing import List, Dict, Optional, Tuple
# 
# from rank_bm25 import BM25Okapi
# 
# from config import DATA_DIR
# 
# BM25_INDEX_FILE = DATA_DIR / "bm25_index.pkl"
# 
# 
# class BM25Service:
#     ...
# 
# bm25_service = BM25Service()