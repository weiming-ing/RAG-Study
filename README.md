## 一、业务背景

**项目名称**：企业知识库 RAG 客服助手

**给谁使用**：企业内部员工。从知识库文档内容来看，涵盖人事入职转正、考勤请假、财务报销、IT故障排查、企业保密规范、公司事务等，说明目标用户是**公司内部全体员工**，覆盖 HR、财务、IT、行政、普通员工等多个角色。

**解决什么问题**：员工在日常工作中遇到流程、制度、操作类问题时，需要反复查阅文档或询问 HR/IT/行政，效率低下。这套系统通过 RAG（检索增强生成）技术，让员工可以用自然语言提问，系统自动从企业文档中检索相关内容并生成准确回答，**降低内部沟通成本，提升信息获取效率**。

**核心链路**：
```
用户提问 → JWT认证 → 意图识别(闲聊/知识库/操作) → 查询优化(LLM改写+规则) 
→ 混合检索(向量+BM25) → Cross-Encoder重排序 → 父文档扩展 
→ [可选: 多轮检索] → LLM流式生成 → Self-RAG事实核查 → 返回答案
```

同时还有一条 **Agent 模式**链路（`/api/agent/chat`），通过 DeepSeek 的 Function Calling 能力，让 LLM 自主决策调用哪些工具（搜索知识库、列出文档、查看统计等），最多迭代 5 轮。

---

## 二、个人职责

如果你是这个项目的**唯一开发者**，那么你对以下所有模块负责：

| 层级 | 模块 | 文件 |
|------|------|------|
| **路由层** | 5个路由模块 | [routes/chat.py](file:///D:/RAG-study/backend/routes/chat.py)、[routes/agent.py](file:///D:/RAG-study/backend/routes/agent.py)、[routes/knowledge.py](file:///D:/RAG-study/backend/routes/knowledge.py)、[routes/session.py](file:///D:/RAG-study/backend/routes/session.py)、[routes/auth.py](file:///D:/RAG-study/backend/routes/auth.py) |
| **服务层** | 11个服务模块 | [services/rag_service.py](file:///D:/RAG-study/backend/services/rag_service.py)、[services/agent_service.py](file:///D:/RAG-study/backend/services/agent_service.py)、[services/knowledge_base.py](file:///D:/RAG-study/backend/services/knowledge_base.py)、[services/llm_service.py](file:///D:/RAG-study/backend/services/llm_service.py)、[services/intent_service.py](file:///D:/RAG-study/backend/services/intent_service.py)、[services/query_optimizer.py](file:///D:/RAG-study/backend/services/query_optimizer.py)、[services/self_rag_service.py](file:///D:/RAG-study/backend/services/self_rag_service.py)、[services/reranker_service.py](file:///D:/RAG-study/backend/services/reranker_service.py)、[services/bm25_service.py](file:///D:/RAG-study/backend/services/bm25_service.py)、[services/session_service.py](file:///D:/RAG-study/backend/services/session_service.py)、[services/tool_registry.py](file:///D:/RAG-study/backend/services/tool_registry.py) + [services/tools.py](file:///D:/RAG-study/backend/services/tools.py) |
| **数据层** | 3种存储 | SQLite（会话日志）、Redis（会话状态）、MySQL（用户账号） |
| **中间件** | JWT认证 | [middleware/auth_middleware.py](file:///D:/RAG-study/backend/middleware/auth_middleware.py) |
| **工具层** | HTTP客户端 | [utils/http_client.py](file:///D:/RAG-study/backend/utils/http_client.py) |
| **前端** | 单页应用 | [frontend/index.html](file:///D:/RAG-study/frontend/index.html)、[frontend/app.js](file:///D:/RAG-study/frontend/app.js)、[frontend/style.css](file:///D:/RAG-study/frontend/style.css) |
| **测试** | 集成测试+RAG评估 | [test_full.py](file:///D:/RAG-study/backend/test_full.py)、[test_rag.py](file:///D:/RAG-study/backend/test_rag.py) |

**参与程度**：全栈独立开发，从后端架构设计、RAG 管线搭建、前端界面到测试用例全覆盖。

---

## 三、请求链路

以一次典型的**知识库问答请求**（`POST /api/chat`）为例：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          用户浏览器 (Frontend)                           │
│                    app.js → fetch /api/chat (SSE)                       │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ Bearer Token
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    FastAPI Server (localhost:8001)                       │
│                                                                         │
│  1. JWTAuthMiddleware → 验证 JWT → 查 MySQL 确认用户存在                  │
│  2. routes/chat.py → chat()                                             │
│     ├─ session_service.add_message()    → Redis (LPUSH messages)        │
│     ├─ session_service.update_title()   → Redis (HSET title)            │
│     ├─ session_service.get_history()    → Redis (LRANGE messages)       │
│     │                                                                   │
│     ├─ 【并发】intent_service.classify()  → DeepSeek API (LLM 意图分类)   │
│     └─ 【并发】query_optimizer.optimize_async() → DeepSeek API (LLM 改写) │
│                                                                         │
│  3. 根据意图路由:                                                         │
│     ├─ intent=chat      → 直接 LLM 生成（不检索）                         │
│     ├─ intent=action    → 本地执行操作（查统计/列文档）                     │
│     └─ intent=knowledge → RAG 检索管线 ─────────────────────┐            │
│                                                              │            │
│  4. RAG 检索管线:                                              │            │
│     ├─ rag_service.retrieve()                                 │            │
│     │   ├─ _hybrid_search()                                   │            │
│     │   │   ├─ 向量检索    → ChromaDB (cosine similarity)     │            │
│     │   │   └─ BM25 检索   → 本地 BM25Okapi 索引              │            │
│     │   │   加权融合: vector*0.7 + bm25*0.3                   │            │
│     │   ├─ _deduplicate() (去重)                              │            │
│     │   ├─ expand_to_parents() → ChromaDB parent_collection   │            │
│     │   └─ reranker.rerank()  → CrossEncoder 本地模型重排序    │            │
│     │                                                         │            │
│     └─ multi_hop_retrieve() [条件触发]                         │            │
│         ├─ LLM 生成补充查询 → DeepSeek API                     │            │
│         └─ 二次检索 + 去重 + 重排序                             │            │
│                                                              │            │
│  5. LLM 流式生成                                              │            │
│     └─ llm_service.generate() → DeepSeek API (SSE streaming)  │            │
│                                                              │            │
│  6. Self-RAG 反思（后台，不阻塞）                                │            │
│     └─ self_rag_service.verify() → DeepSeek API (事实核查)     │            │
│                                                              │            │
│  7. 保存回复                                                   │            │
│     └─ session_service.add_message() → Redis (RPUSH)          │            │
└──────────────────────────────────────────────────────────────────────────┘
```

**涉及的服务/存储总结**：

| 组件 | 用途 | 调用方式 |
|------|------|----------|
| **DeepSeek API** | LLM 生成、意图分类、查询改写、多轮检索补充查询、Self-RAG 验证、文档摘要生成 | HTTP (httpx) |
| **ChromaDB** | 向量存储与检索（3个collection: 子块/父块/摘要） | 本地持久化 (chroma.sqlite3) |
| **BM25 索引** | 关键词稀疏检索 | 本地 pickle 文件 (bm25_index.pkl) |
| **Cross-Encoder** | 检索结果重排序 (BAAI/bge-reranker-base) | 本地 CPU 推理 |
| **Sentence Transformer** | 文本向量化 (BAAI/bge-small-zh-v1.5) | 本地 CPU 推理 |
| **Redis** | 会话元数据 + 消息历史存储 | TCP (localhost:6379) |
| **MySQL** | 用户账号存储 (users表) | TCP (localhost:3306) |
| **SQLite** | 旧版会话存储（已迁移到Redis，但初始化代码仍在） | 本地文件 (rag_assistant.db) |

---

## 四、技术选型

| 技术选型 | 方案 | 对比过的方案 | 代价 |
|----------|------|-------------|------|
| **Web框架** | FastAPI (Python) | Flask / Django | 学习成本低，异步支持原生，但生态不如 Django 成熟，无 ORM 需手写 SQL |
| **LLM** | DeepSeek API (deepseek-v4-flash) | OpenAI / 本地 Ollama | 依赖外部 API，有网络延迟和费用；但无需 GPU 部署，模型能力强 |
| **Embedding** | BAAI/bge-small-zh-v1.5 (本地CPU) | text2vec / m3e / OpenAI Embedding | 中文效果好，但 CPU 推理较慢，首次加载需下载模型（~100MB） |
| **向量数据库** | ChromaDB (本地持久化) | Milvus / Qdrant / FAISS | 轻量零配置，但单机性能有限，不支持分布式 |
| **Reranker** | BAAI/bge-reranker-base (Cross-Encoder) | Cohere Rerank API / 无重排序 | 显著提升检索精度，但增加额外推理延迟 |
| **混合检索** | 向量(0.7) + BM25(0.3) | 纯向量 / 纯BM25 | 互补效果好，但需要维护 BM25 索引一致性 |
| **会话存储** | Redis | SQLite / 内存 | 高性能、支持过期，但需要额外部署 Redis 服务 |
| **用户认证** | JWT + bcrypt + MySQL | OAuth2 / Session Cookie | 无状态认证，但需要管理 token 刷新逻辑 |
| **前端** | 原生 HTML/CSS/JS | React / Vue | 零构建步骤，但代码组织和可维护性差 |
| **父文档检索** | 小块检索(300字) + 大块生成(1000字) | 固定大小分块 | 检索精度高、上下文完整，但存储量翻倍 |
| **Agent模式** | DeepSeek Function Calling | LangChain Agent / 自研 | 实现简单，但受限于模型能力，复杂推理可能偏差 |

**关键设计决策**：
- **父子文档分块**：用小块（~300字）做精确向量检索，命中的小块映射到父块（~1000字），用父块内容作为 LLM 上下文，兼顾检索精度和上下文完整性
- **意图路由**：先规则快速匹配（无成本），未命中再用 LLM 分类，减少不必要的 API 调用
- **查询优化双模式**：优先 LLM 改写，失败回退到规则改写，保证可用性

---

## 五、难点或故障

**潜在难点与排查思路**：

1. **Embedding 模型首次加载慢**
   - 现象：服务启动后首次上传文档时卡住
   - 定位：查看日志 `[WARNING] 模型预加载失败`
   - 原因：HuggingFace 模型下载慢（国内网络问题）
   - 修复：配置了 `HF_ENDPOINT="https://hf-mirror.com"` 镜像；在 `lifespan` 中调用 `preload()` 预加载
   - 验证：启动后日志显示加载成功，无需等待

2. **BM25 索引与向量库不一致**
   - 现象：上传文档后 BM25 检索不到新内容
   - 定位：检查 `bm25_index.pkl` 文件时间戳
   - 修复：`_notify_bm25()` 在上传后清空 BM25 缓存，下次检索时自动重建
   - 验证：上传文档后观察 `[BM25] 索引构建完成` 日志

3. **多轮检索触发过于频繁**
   - 现象：每次查询都触发多轮检索，LLM 调用增加
   - 定位：检查 `MULTI_HOP_MIN_SCORE` 和 `MULTI_HOP_MIN_SOURCES` 配置
   - 修复：调高阈值（当前 `min_score=0.6`, `min_sources=3`）
   - 验证：通过 `test_rag.py` 观察检索日志

4. **Self-RAG 验证误报**
   - 现象：事实核查频繁提示"可信度较低"
   - 定位：检查 `SELF_RAG_CONFIDENCE_THRESHOLD` 配置
   - 修复：调低阈值（当前 `0.5`），或检查验证 prompt 是否合理
   - 验证：观察生成结果末尾的警告信息

5. **Redis 连接失败导致服务不可用**
   - 现象：会话列表为空、无法创建会话
   - 定位：启动日志 `[WARNING] Redis 连接失败`
   - 修复：确保 Redis 服务运行；配置正确的 `REDIS_HOST`/`REDIS_PORT`
   - 验证：`GET /api/health` 返回正常

---

## 六、项目指标

**当前可量化的指标**：

| 指标 | 数据来源 | 统计口径 | 对照条件 |
|------|---------|---------|---------|
| **检索延迟** | `test_rag.py` 中 `evaluate_retrieval()` 打点 | 单次混合检索端到端耗时（含向量+BM25+重排序） | 不同 top_k 值、开关混合检索 |
| **关键词召回率** | `test_rag.py` 中 `evaluate_keyword_recall()` | 检索结果中包含预期关键词的比例 | 不同查询改写策略 |
| **知识库规模** | `GET /api/knowledge/statistics` | 文档数、分块数、总大小 | 上传前后对比 |
| **LLM 生成质量** | Self-RAG 验证的 `confidence` 分数 | 0-1 的可信度评分 | 不同检索策略、不同 chunk_size |
| **意图分类准确率** | 人工标注 vs 系统分类 | chat/knowledge/action 三分 | 规则快速匹配 vs LLM 分类 |
| **测试用例通过率** | `test_full.py` | 17 个测试用例的通过/失败 | 不同环境 |

**关键说明**：
- 当前**没有生产环境数据**，所有指标来自 `test_rag.py` 的离线评估和 `test_full.py` 的集成测试
- 5 个测试用例覆盖了制度流程类、操作指南类、事实类、清单类、精确匹配类查询
- 建议补充：人工标注的 Q&A 对（ground truth），用于计算 MRR、NDCG、Hit Rate 等标准检索指标

---

## 七、职责范围

如果你是**唯一开发者**，则全部由你负责。但若按团队分工的理想划分：

| 模块 | 职责划分 | 说明 |
|------|---------|------|
| **基础设施** | 运维/SRE 同事 | Redis 部署运维、MySQL 部署运维、服务器环境配置 |
| **LLM API** | DeepSeek 官方 | 模型推理、API 网关、Token 计费 |
| **Embedding/Reranker 模型** | BAAI 团队（开源） | 预训练模型提供，本地推理在本项目内完成 |
| **知识库文档** | 各业务部门（HR/IT/财务/行政） | 提供和维护 Markdown 文档内容 |
| **前端 UI** | 你（或前端同事） | 当前为原生实现，后续可拆分为独立前端项目 |
| **后端服务** | 你 | 全部业务逻辑：RAG 管线、Agent、认证、会话管理 |
| **数据层** | 你 | SQLite/Redis/MySQL 的 schema 设计和初始化 |
| **测试** | 你 | 集成测试 (test_full.py) + RAG 评估 (test_rag.py) |

---

## 总结

这是一个**全栈独立开发**的企业级 RAG 项目，技术栈选型务实（轻量 ChromaDB + 免费 DeepSeek API + 本地 CPU 推理）
，RAG 管线设计完整（意图路由 → 查询改写 → 混合检索 → 重排序 → 父文档扩展 → 多轮检索 → Self-RAG 验证）
，同时提供了 Agent 模式作为进阶功能。当前处于**开发/演示阶段**，缺少生产环境监控和标准化的检索质量评估体系。