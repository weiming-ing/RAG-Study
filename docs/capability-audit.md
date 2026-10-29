# RAG 助手 — 接线审计清单

> 生成日期：2026-10-19 | 最近更新：2026-10-24 | 审计范围：26 张表、24 个 Service、19 个 Controller
>
> 状态标记：🟢 已接通 | 🟡 部分接通 | 🔴 仅配置/死代码 | ✅ 已修复（2026-10-19）

## 修复记录（2026-10-24 迭代）

| # | 修复项 | 涉及文件 | 状态 |
|---|--------|----------|------|
| G1 | **向量路径 kbId 过滤失效修复**（payload 存整数、matchKeyword 只匹配字符串，导致权限过滤静默失效） | `VectorStoreServiceImpl.java`（新增 `buildTypeAgnosticMatch`：字符串 OR 整数双分支匹配） | ✅ |
| G2 | Agent 模式检索接入 kb_id 权限过滤 | `agent/route.py`、`agent/core.py`、`agent/tools/base.py` | ✅ |
| G3 | 语义缓存按 kb_id 隔离 + 存取口径统一（store 原用 raw query、lookup 用改写后 query）+ 修 3 个存量 bug（淘汰排序 r.ttl 未 await、漏删 sc:idx、KEYS→SCAN） | `services/semantic_cache.py`、`routes/chat.py` | ✅ |
| G4 | 访客问答补全 RAG 链路（原实现不检索、无鉴权、无限流；现按 GUEST_KB_IDS 白名单检索，空则 fail closed 退化为闲聊） | `routes/chat.py`、`config.py` | ✅ |
| G5 | Python 侧对话限流（原 SecurityCheckFilter 只覆盖 Java API，/api/chat 裸奔） | 新增 `middleware/rate_limit_middleware.py`（Redis 滑动窗口，user/IP 维度） | ✅ |
| G6 | Docling 同步解析阻塞事件循环（解析期间全部并发请求卡死） | `routes/knowledge.py` 两处 `asyncio.to_thread` | ✅ |
| G7 | 敏感词接入对话链路 | 新增 `InternalSecurityController.java`（/api/internal/security/sensitive-check），`routes/chat.py` 检索前调用 | ✅ |
| G8 | 会话越权（get_history/rename_session 不校验归属） | `routes/session.py`（`_ensure_owner`）、`services/session_service.py`（`get_session_owner`） | ✅ |
| G9 | 文档上传异步化（接通零调用的 ParseTaskService 状态机 + parseTaskExecutor 线程池；上传立即返回 PARSING，前端轮询） | 新增 `DocumentProcessService.java`，改 `KnowledgeBaseService.java`、`DocList.vue`、`DocDetail.vue` | ✅ |
| G10 | 检索评测基准重建（旧 test_rag.py sources=[] 硬编码恒 0%） | 重写 `test_rag.py`：直连 /api/internal/search 计算 MRR/NDCG@10/HitRate@3 | ✅ |
| G11 | Self-RAG 模式开关 off/log/corrective（核实主链路 verify_with_reflection 已有闭环，本项为行为模式化） | `config.py`、`routes/chat.py` | ✅ |
| G12 | **KB 级阈值误杀修复**：similarityThreshold（原始相似度语义）作用于加权后分数（×0.7 后全部低于阈值），kbId 路径恒 0 命中 | `HybridSearchService`（merge 时 metadata 保留 `vectorScore` 原始分）、`KnowledgeSearchService`（阈值改用原始分比较） | ✅ |
| G13 | HSET 多字段语法兼容（Redis 4.0+ 语法在本地 Redis 3.2 报 wrong number of arguments，会话创建 500） | `session_service.py`（`_hset_all` 逐字段写） | ✅ |
| G14 | **Redis 密码缺失导致静默降级**：backend/.env `REDIS_PASSWORD` 为空而本地 Redis 配了 requirepass，会话/语义缓存/限流长期在 SQLite 降级模式下运行且无告警（lifespan 的 check_redis 吞异常后仍打印"Redis 连接成功"） | `backend/.env` 补齐密码；**遗留改进项：check_redis 失败时日志应为 ERROR 并在 /api/health 暴露真实状态** | ✅/⚠️ |
| G15 | 限流中间件顺序错误：Starlette 先添加的在更内层（构建时反序包裹），RateLimit 加在 JWT 之后反而在最外层先执行，读不到 `request.state.user`，登录用户被按 IP 计数 | `main.py`（RateLimit 改为最先添加） | ✅ |
| G16 | 语义缓存键改用原始 query：optimized_query 依赖会话历史（LLM 改写随轮次漂移），跨轮不稳定导致永不命中 | `routes/chat.py`（lookup/store 均用 raw query） | ✅ |
| G17 | **异步上传事务竞态**：@Transactional 上传方法在事务内直接提交 @Async 任务，parse 线程 selectById 读不到未提交行（"找不到记录"）静默放弃——批量上传 6 份文档仅 1 份侥幸成功 | `KnowledgeBaseService`（新增 `submitAfterCommit`：afterCommit 回调后再提交异步任务） | ✅ |
| G18 | 环境治理：check_redis 吞异常后仍打印"连接成功"（G14 根因）→ 改为按 REDIS_AVAILABLE 如实告警 ERROR 并在 /api/health 暴露 `{available, error}`；`UVICORN_RELOAD` 默认 true → 改为默认 false（reload 会孤儿化 worker 抢占端口）；Redis 版本 < 4.0 启动时打 WARNING | `services/session_service.py`、`main.py` | ✅ |
| G19 | **本地 Redis 3.2 升级 7.4**：IDE 自带的 redis-server 3.2.100 不支持多字段 HSET（G13 根因），已替换为 Docker 容器 `rag-redis7`（redis:7-alpine，`--requirepass` 沿用 backend/.env 原密码，AOF 持久化 + `--restart unless-stopped`，数据卷 `rag-redis-data`）；G13 的逐字段兼容代码保留（对 7.x 无害，兼顾老环境） | 本机 Docker；`test_full.py` 18/18 复验通过 | ✅ |
| G20 | **知识库三级访问隔离（公共级/员工级/管理级）**：`kb_knowledge_base` 新增 `visibility` 列（PUBLIC/EMPLOYEE/MANAGEMENT，迁移脚本 `db/migrate-kb-access.sql`，存量按 is_public 忠实映射）；检索范围改由**服务端强制**——Java 新增 `GET /api/internal/knowledge-bases/accessible` 解析用户可见集合，Python `services/kb_access.py`（60s TTL）解析后以 `filters["kbIds"]` 下发（Qdrant `matchKeywords/matchValues` OR 组 + BM25 集合包含双路过滤）；KB 列表/详情/文档 12 个端点接入 `assertKbReadable/assertKbWritable`；修复授权接口越权（原任何登录用户可给任何 KB 授权）；语义缓存 scope 改为检索范围键（`set:md5`）；修复 KB 创建/更新代理丢弃 visibility 字段 | Java: `KnowledgeBaseManageService`/`KnowledgeBaseController`/`SearchRequest`/`VectorStoreServiceImpl`/`Bm25ServiceImpl`/`DocumentController`；Python: `kb_access.py`/`rag_service.py`/`chat.py`/`agent/`；前端: `KbList.vue`/`KbConfig.vue` | ✅ |

## 端到端验证记录（2026-10-24）

| 验证项 | 结果 |
|--------|------|
| 敏感词内部端点 + token 门禁（401） | ✅ |
| kbId 向量路径过滤（过滤后 vectorHits>0，错 kbId=0，修复前向量路径恒 0） | ✅ |
| 上传异步化（1.79s 返回 processing → 1.5s indexed，parse_task 表 progress=100） | ✅ |
| 限流 429（访客第 2 次/分钟触发，Redis 正常计数，fail-open 0 次） | ✅ |
| 会话越权 404 + test_full 18/18 | ✅ |
| 语义缓存（第 1 次 mode=rag 9.4s → 第 2 次 mode=cache 2.75s；命中延迟 ~2.5s 主因是 Java embed HTTP ~600ms，README 的 ~50ms 估算未计入） | ✅ |
| 访客 RAG（GUEST_KB_IDS=16 时免登录返回带引用 sources） | ✅ |
| 检索评测（MRR/NDCG/HitRate 报告落 evaluation/retrieval_report.md；**导入 6 份制度文档后真实基线：MRR 0.50 / NDCG@10 0.77 / HitRate@3 0.85**，此前低分系语料缺失） | ✅ |
| 批量上传 6 份文档全部 READY + parse_task SUCCESS（暴露并修复 G17 事务竞态） | ✅ |
| **三级隔离**（`test_kb_isolation.py` 6/6）：普通用户带管理级 kb_id → 403；默认检索不泄漏管理级内容；访客仅 PUBLIC；非授权人调用授权接口被拒；owner 授权后 ≤60s 生效可检索；kbIds 多值过滤/范围外返回 0 | ✅ |

**离线回归**：`backend/test_security_fixes.py`（缓存隔离/淘汰/限流 429/fail open，stub Redis，无需起服务）；**在线冒烟**：`backend/test_kb_filter.py`（kbId 过滤双向断言）、`backend/test_full.py`（新增越权访问 404 用例）。

## 修复记录（2026-10-19）

| # | 修复项 | 涉及文件 | 状态 |
|---|--------|----------|------|
| F1 | 删除文档清理父块集合 | `KnowledgeBaseService.java` (deleteDocument/purgeDocument/reparseDocument) | ✅ |
| F2 | 删除知识库级联清理 | `KnowledgeBaseManageService.java` (deleteKb, 新增 chunkMapper/vectorStoreService/bm25Service 依赖) | ✅ |
| F3 | BM25 支持 kbId/documentId 过滤 | `Bm25Service.java` (IndexEntry 新增字段), `Bm25ServiceImpl.java` (存储+过滤+search overload) | ✅ |
| F4 | 检索过滤传递 kbId | `HybridSearchService.java` (BM25 分支传 filters), `rag_service.py` (_java_search 接受 kb_id, ChatRequest 新增 kb_id), `chat.py` (传递 kb_id) | ✅ |
| F5 | 引用字段映射统一 | `rag_service.py` (_java_search 统一输出 doc_id/chunk_id/chunk_index/kb_id) | ✅ |
| F6 | 父块扩展修复（向量路径填充 parentContent） | `KnowledgeBaseService.java` (索引时 payload 加 parentContent+chunkIndex), `VectorStoreServiceImpl.java` (search 提取 parentContent/chunkId/parentChunkId) | ✅ |
| F7 | Token 统计修正 | `chat.py` (CJK-aware _estimate_tokens 替代字符数÷4) | ✅ |
| F8 | updateChunk 路径 BM25 全字段索引 | `KnowledgeBaseService.java` (updateChunk 改用 IndexEntry 全字段) | ✅ |

### 待修复（P1-P3）

| 序 | 修复项 | 严重度 |
|---|--------|--------|
| P1 | KB 级检索配置生效（vector_weight/bm25_weight 等） | ✅ |
| P2 | 限流/访问控制/API Key 鉴权接通 | ✅ |
| P3 | README 修正 | ✅ |
| P3 | 评测集重建 | ✅ |

---

## 一、检索管线

| 组件 | 状态 | 举证 |
|------|------|------|
| `KnowledgeSearchService` (检索门面) | 🟢 | `SearchController` → `/api/internal/search`，被 Python `rag_service._java_search()` 调用 |
| `HybridSearchService` (向量+BM25 融合) | 🟢 | 被 `KnowledgeSearchService` 和 `MultiHopService` 调用；CompletableFuture 并行执行 |
| `VectorStoreServiceImpl.search` (Qdrant 向量检索) | 🟢 | 被 `HybridSearchService` 调用；支持 filter 透传 |
| `Bm25ServiceImpl.search` (Lucene BM25) | 🟢 ✅ | 被 `HybridSearchService` 调用；**现已支持 filter 参数和 kbId/documentId 过滤** |
| `RerankerService` (重排序) | 🟡 | 被 `KnowledgeSearchService` 和 `MultiHopService` 调用；但实现是 **bi-encoder 二次打分**（`0.6×余弦 + 0.4×原始分`），不是 Cross-Encoder |
| `MultiHopService` (多跳检索) | 🟡 | 被 `KnowledgeSearchService.multiHopSearch()` 调用；但实现是**启发式关键词扩展、固定 2 轮、无 LLM** |
| `EmbeddingService` (ONNX 本地向量化) | 🟢 | bge-small-zh，512 维，被索引和检索同时使用 |

### 检索管线已知缺陷

| # | 缺陷 | 严重度 | 详情 |
|---|------|--------|------|
| 1 | **检索无权限过滤** | 🟡 部分修复 | Python 侧已传 kbId filter；BM25 已支持过滤；向量检索 Qdrant filter 已就绪。**前端需传 kb_id**（已加字段） |
| 2 | **父块扩展未生效** | ✅ 已修复 | `VectorStoreServiceImpl.search` 现从 payload 提取 `parentContent`；索引时 child payload 已写入 `parentContent`；Python 侧优先使用 `parentContent` |
| 3 | **KB 级检索配置不生效** | ✅ 已修复 | `SearchRequest` 新增 `kbId`，`KnowledgeSearchService.searchWithKbConfig` 加载 KB 配置覆盖全局权重/阈值/filterLowScore，`HybridSearchService.hybridSearch` 接受 customVectorWeight/customBm25Weight |
| 4 | **引用字段映射不一致** | ✅ 已修复 | `rag_service.py` 统一输出 `doc_id`/`chunk_id`/`chunk_index`/`kb_id`；Java `VectorStoreServiceImpl` 和 `Bm25ServiceImpl` 均填充 `chunkId`/`documentId`/`kbId` 到 metadata |

---

## 二、文档/知识库管理

| 组件 | 状态 | 举证 |
|------|------|------|
| `KnowledgeBaseService` (文档索引/删除) | 🟢 ✅ | `DocumentController` 调用；**deleteDocument/purgeDocument/reparseDocument 现已清理父块集合** |
| `KnowledgeBaseManageService` (知识库管理) | 🟢 ✅ | `KbManageController` 调用；**deleteKb 现已级联删除文档/切片/Qdrant/BM25** |
| `DocumentChunker` (文档切片) | 🟢 | 父子切片策略（child=300, parent=1000, overlap=50），被索引流程调用 |
| `ChunkService` (切片管理) | 🟢 | `ChunkController` 调用：查看、编辑、拆分、合并、删除向量、重建向量 |
| `ParseTaskService` (解析任务) | 🔴 | `createTask()` **零调用**；`AsyncTaskConfig` 的两个线程池 Bean **无人注入**；文档入库是**请求内同步执行** |

### 管理已知缺陷

| # | 缺陷 | 严重度 | 详情 |
|---|------|--------|------|
| 5 | **删除文档不清父块集合** | ✅ 已修复 | `deleteDocument`/`purgeDocument`/`reparseDocument` 现已清理 `rag_knowledge_parent` 父块集合 |
| 6 | **删除知识库不清任何内容** | ✅ 已修复 | `deleteKb` 现已级联删除文档→切片→Qdrant(含父块集合)→BM25→DB |
| 7 | **解析任务异步化未接通** | 🟠 形态 | `createTask()` 零调用、线程池 Bean 零注入；表面有状态机（PENDING→PROCESSING→COMPLETED），实际全部同步执行 |

---

## 三、安全模块

| 组件 | 状态 | 举证 |
|------|------|------|
| `JwtAuthFilter` (JWT 认证) | 🟢 | Spring Security Filter Chain 中注册，`/api/internal/**` 放行 |
| `RateLimitService` (限流) | 🟢 ✅ | `SecurityCheckFilter` L121/L131 按 USER(IP)/ENDPOINT 两维度调用 `checkLimit()`（2026-10-24 核实；注：限流计数在内存，重启清零、多实例不共享） |
| `AccessControlService` (访问控制) | 🟢 ✅ | `SecurityCheckFilter` L60-74 调用 `isBlocked()`/`isWhitelisted()`（2026-10-24 核实） |
| `ApiKeyService` (API Key) | 🟢 ✅ | `SecurityCheckFilter` L77-118 调用 `validate()` + 日限额 + `recordUsage()`（2026-10-24 核实） |
| `SensitiveWordService` (敏感词) | 🟢 ✅ | 新增内部端点 `/api/internal/security/sensitive-check`（`InternalSecurityController`），Python `chat.py`/`guest_chat` 检索前调用（2026-10-24） |
| `AuditLogService` (审计日志) | 🟢 | 被 `KnowledgeBaseService`、`ChunkService`、`TestDataGeneratorController`、`AuditLogController` 多处调用 |
| `SysConfigService` (系统配置) | 🟡 | CRUD 正常（`SysConfigController` 调用）；但 `@Cacheable("sysConfig")` **无效**：全仓库无 `@EnableCaching`、无 `spring-boot-starter-cache` |
| `SysLogService` (系统日志) | 🟢 | `SysLogController` 调用：日志列表、统计、清理 |

### 安全模块已知缺陷

| # | 缺陷 | 严重度 | 详情 |
|---|------|--------|------|
| 8 | **限流未接通（Java 侧）** | ✅ 已修复 | `SecurityCheckFilter` 已调用 `checkLimit()`；注意仅覆盖 Java 对外 API——Python 主链路限流见 G5（新增 `rate_limit_middleware.py`） |
| 9 | **访问控制未接通** | ✅ 已修复 | `SecurityCheckFilter` 已调用 `isBlocked()/isWhitelisted()` |
| 10 | **API Key 鉴权未接通** | ✅ 已修复 | `SecurityCheckFilter` 已调用 `validate()`，X-API-Key 请求可鉴权 |
| 11 | **缓存未启用** | 🟠 性能 | `@Cacheable("sysConfig")` 注解存在但 Spring Cache 基础设施缺失 |
| 12 | **敏感词不拦截对话** | ✅ 已修复 | 新增 `/api/internal/security/sensitive-check`，Python 对话链路（含访客）检索前调用，命中即拒绝（G7） |

---

## 四、对话/统计模块

| 组件 | 状态 | 举证 |
|------|------|------|
| `ConversationLogService` (对话日志) | 🟢 | `ConversationController` 调用：列表、分组、引用追踪、反馈、统计趋势、排行榜 |
| `DashboardService` (仪表盘) | 🟢 | `DashboardController` 调用：概览、API 统计、Token 统计、热榜、告警；Python `chat.py` 通过 `record_api_call/record_doc_hit/record_token_usage` 写入 |
| `UserService` (用户管理) | 🟢 | `UserController` 调用；RBAC 体系正常 |
| `RoleService` (角色管理) | 🟢 | `RoleController` 调用 |
| `MenuService` (菜单管理) | 🟢 | `MenuController` 调用 |
| `DebugService` (调试) | 🟢 | `DebugController` 调用：测试用例管理、检索调试 |

### 对话/统计已知缺陷

| # | 缺陷 | 严重度 | 详情 |
|---|------|--------|------|
| 13 | **Token 统计用字符数÷4** | ✅ 已修复 | `chat.py` 现用 CJK-aware `_estimate_tokens`：中文 ~1.5 token/字，非中文 ~0.25 token/字 |
| 14 | **引用去重/统计字段已统一** | ✅ 已修复 | `rag_service.py` 统一输出 `doc_id`/`chunk_id`/`chunk_index`/`kb_id`；`chat.py` 统一读取 `chunk_id`/`doc_id` |

---

## 五、文档与现实差距

| # | 问题 | 文档描述 | 实际实现 |
|---|------|----------|----------|
| 15 | **README 声称 Cross-Encoder reranker** | ✅ 已修正 | 全局修正：ChromaDB→Qdrant、pickle BM25→Lucene、CrossEncoder→bi-encoder 二次打分、增加了 Spring Boot + Vue 3 架构描述 |
| 16 | **README 声称 LLM 多跳** | ✅ 已修正 | 修正为"启发式关键词扩展 + 固定 2 轮" |
| 17 | **README 声称父块扩展** | README 描述"小块检索、大块生成" | ✅ **已修复**：`VectorStoreServiceImpl.search` 现从 payload 提取 `parentContent`；索引时 child payload 已写入 `parentContent`；Python 侧优先使用 `parentContent`——LLM 现可拿到 1000 字父块而非 300 字子块 |

---

## 六、汇总

### 接线状态分布

| 状态 | 数量 | 组件 |
|------|------|------|
| 🟢 已接通 | 24 | KnowledgeSearchService, HybridSearchService, VectorStoreServiceImpl, Bm25ServiceImpl, EmbeddingService, DocumentChunker, ConversationLogService, DashboardService, ChunkService, AuditLogService, DebugService, SysLogService, UserService, RoleService, MenuService, KnowledgeBaseService, KnowledgeBaseManageService, SensitiveWordService, **RateLimitService**, **AccessControlService**, **ApiKeyService**, **SysConfigService** (含缓存) |
| 🟡 部分接通 | 1 | RerankerService (bi-encoder 而非 cross-encoder), MultiHopService (启发式而非 LLM) |
| 🔴 仅配置/死代码 | 0 | 无 |

### 已修复（2026-10-19 迭代）

| 序 | 修复项 | 涉及文件 | 状态 |
|---|--------|----------|------|
| P0 | 检索权限过滤（含 BM25 分支） | `Bm25Service`, `Bm25ServiceImpl`, `HybridSearchService`, `rag_service.py`, `schemas.py`, `chat.py` | ✅ |
| P0 | 删除文档清理父块集合 | `KnowledgeBaseService.deleteDocument/purgeDocument/reparseDocument` | ✅ |
| P0 | 删除 KB 级联清理 | `KnowledgeBaseManageService.deleteKb` | ✅ |
| P0 | 引用字段映射修正 | `rag_service.py`, `VectorStoreServiceImpl.search` | ✅ |
| P1 | 父块扩展修复（向量路径填充 parentContent+chunkIndex） | `VectorStoreServiceImpl.search`, `KnowledgeBaseService` | ✅ |
| P2 | Token 统计修正（CJK-aware 估算） | `chat.py` (_estimate_tokens) | ✅ |
| P2 | updateChunk 路径 BM25 全字段索引 | `KnowledgeBaseService.updateChunk` | ✅ |
| P1 | KB 级检索配置生效 | `KnowledgeSearchService.searchWithKbConfig`, `HybridSearchService.hybridSearch`, `SearchRequest`, `SearchController`, `rag_service.py` | ✅ |
| P2 | 缓存基础设施补齐 | `pom.xml` (spring-boot-starter-cache + Caffeine), `RagEngineApplication` (@EnableCaching), `CacheConfig.java` (10min TTL/1000 条目) | ✅ |
| P2 | 访问控制 + 限流 + API Key 鉴权接通 | `SecurityCheckFilter.java` (IP 黑白名单/AccessControl, USER+ENDPOINT 限流/RateLimit, X-API-Key 鉴权/ApiKey), `SecurityConfig.java` (注册到 Filter 链) | ✅ |
| P3 | 评测集重建 | `evaluation/test_cases.json` (20 用例, 5 个坏例子), `evaluation/grader.py` (LLM Grader), `evaluation/run_eval.py` (主评测脚本) | ✅ |

### 已知限制（无需立即修复）
- JwtAuthFilter 与 SecurityCheckFilter 均不拦截：当同时存在 API Key 和 JWT 时，API Key 优先
- 限流桶为内存实现，多实例部署时不共享；建议生产环境换 Redis 令牌桶
- API Key 的 kbIds 字段仅存储，未在检索链路按 kbIds 过滤检索范围