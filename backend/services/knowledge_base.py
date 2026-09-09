"""
知识库管理服务（已迁移至 Java 后端）

原因：文档管理、切片、向量化、存储等功能需要高性能 Java 处理管道，
已统一迁移至 Java 后端 KnowledgeBaseService.java。

Java 后端负责：文档解析（Apache Tika）、文档分块（DocumentChunker）、
Embedding 向量化（ONNX Runtime）、向量存储（Qdrant）、父子文档分块策略。

Python 前端通过 http_client 调用 Java 后端 API:
  - POST   /api/internal/knowledge/upload     文档上传
  - GET    /api/internal/knowledge/list        文档列表
  - GET    /api/internal/knowledge/{id}        文档详情
  - DELETE /api/internal/knowledge/{id}        删除文档
  - GET    /api/internal/knowledge/statistics  统计信息
"""

# 知识库管理已迁移至 Java 后端 (KnowledgeBaseService.java)
# Java 后端负责：文档管理、文档分块、Embedding向量化、向量存储(Qdrant)、父子文档分块
# Python 前端通过 http_client 调用 Java 后端 API:
#   - POST /api/internal/knowledge/upload  (文档上传)
#   - GET  /api/internal/knowledge/list     (文档列表)
#   - GET  /api/internal/knowledge/{id}     (文档详情)
#   - DELETE /api/internal/knowledge/{id}   (删除文档)
#   - GET  /api/internal/knowledge/statistics (统计信息)

# import os
# import uuid
# import shutil
# import json
# import re
# import asyncio
# import httpx
# from datetime import datetime
# from pathlib import Path
# from typing import List, Optional, Set
# ...
# class KnowledgeBaseService:
#     ...
# knowledge_base_service = KnowledgeBaseService()