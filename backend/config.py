import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# 配置来源（显式路径，避免因启动目录不同而读到不同的 .env ——
# 曾出现 backend/.env 与仓库根 .env 的 JWT 密钥不一致的问题）：
#   1) backend/.env —— 本地开发补充项
#   2) 仓库根 .env —— 与 docker-compose 共用的配置源
# 真实环境变量优先级最高：load_dotenv 默认不覆盖已存在的环境变量，
# 因此容器/宿主注入的值始终胜出。
load_dotenv(BASE_DIR / "backend" / ".env")
load_dotenv(BASE_DIR / ".env")

# 数据目录（支持通过环境变量覆盖，Docker 环境中使用 /app/data）
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
DOCUMENTS_DIR = DATA_DIR / "documents"
CHROMA_DIR = DATA_DIR / "chroma_db"
DB_PATH = DATA_DIR / "rag_assistant.db"

# 确保目录存在
for dir_path in [DATA_DIR, DOCUMENTS_DIR, CHROMA_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Embedding 配置
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-small-zh-v1.5")
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")

# 父文档检索配置（小块检索 + 大块生成）
CHILD_CHUNK_SIZE = 300
CHILD_CHUNK_OVERLAP = 50
PARENT_CHUNK_SIZE = 1000
PARENT_CHUNK_OVERLAP = 100

# 兼容旧配置
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# 文档摘要配置
ENABLE_DOC_SUMMARY = True
SUMMARY_MAX_CHUNKS = 5

# LLM 查询改写配置
ENABLE_LLM_QUERY_REWRITE = False

# Agent 进阶配置
ENABLE_INTENT_ROUTING = True
ENABLE_MULTI_HOP = True
ENABLE_SELF_RAG = True
MULTI_HOP_MIN_SCORE = 0.6
MULTI_HOP_MIN_SOURCES = 3
SELF_RAG_CONFIDENCE_THRESHOLD = 0.5
SELF_RAG_MAX_RETRIEVAL_ATTEMPTS = 1
SELF_RAG_VERIFY_TIMEOUT = 8.0
# Self-RAG 运行模式：
#   off        —— 不做验证（最低延迟）
#   log        —— 后台验证仅记日志，不阻塞响应、不修正回答
#   corrective —— 验证不充分时同步补充检索并重新生成（默认，增加最多 VERIFY_TIMEOUT 秒延迟）
SELF_RAG_MODE = os.getenv("SELF_RAG_MODE", "corrective").lower()

# Agent 模式配置
ENABLE_AGENT_MODE = True
AGENT_MAX_ITERATIONS = 5
AGENT_CONFIDENCE_THRESHOLD = 0.3

# 语义缓存配置
SEMANTIC_CACHE_ENABLED = os.getenv("SEMANTIC_CACHE_ENABLED", "true").lower() == "true"
SEMANTIC_CACHE_THRESHOLD = float(os.getenv("SEMANTIC_CACHE_THRESHOLD", "0.92"))
SEMANTIC_CACHE_TTL = int(os.getenv("SEMANTIC_CACHE_TTL", "86400"))

# 访客问答的附加限制（逗号分隔的 kb_id），与 PUBLIC 级知识库取交集。
# 访客的基础范围由服务端强制为 visibility=PUBLIC 的知识库（见 services/kb_access.py）；
# 本配置非空时进一步收窄到交集，为空表示不附加限制（即全部 PUBLIC 库）。
# 交集为空时 fail closed：访客不检索任何知识库，退化为闲聊。
GUEST_KB_IDS = [s.strip() for s in os.getenv("GUEST_KB_IDS", "").split(",") if s.strip()]

# 对话链路限流（Redis 滑动窗口，仅作用于 /api/chat、/api/chat/guest、/api/agent/chat）。
# 登录用户按 user_id 计数，访客按 client IP 计数；Redis 不可用时 fail open。
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_USER_PER_MIN = int(os.getenv("RATE_LIMIT_USER_PER_MIN", "20"))
RATE_LIMIT_GUEST_PER_MIN = int(os.getenv("RATE_LIMIT_GUEST_PER_MIN", "5"))

# 敏感词检查：对话（含访客）在检索前调用 Java 敏感词服务，命中即拒绝回答。
# Java 不可达时 fail open（放行并记日志），不阻断主链路。
ENABLE_SENSITIVE_WORD_CHECK = os.getenv("ENABLE_SENSITIVE_WORD_CHECK", "true").lower() == "true"

# 检索配置
TOP_K = int(os.getenv("TOP_K", "5"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.3"))
USE_HYBRID_SEARCH = os.getenv("USE_HYBRID_SEARCH", "true").lower() == "true"
VECTOR_WEIGHT = float(os.getenv("VECTOR_WEIGHT", "0.7"))
BM25_WEIGHT = float(os.getenv("BM25_WEIGHT", "0.3"))

# LLM 配置（OpenAI 兼容端点）
# 任何实现 /v1/chat/completions 的服务都可直接替换，无需改代码：
#   vLLM / Ollama / LMDeploy / Xinference / 国产云 API 兼容模式 / One-API 网关
#
# 变量名：优先读通用名 LLM_*，回落到历史名 DEEPSEEK_*（两者都支持，便于平滑迁移）。
# base_url 带不带结尾 /v1 都兼容，见 utils/http_client.py 的 _url()。
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 向后兼容别名：现有代码与既有 .env 继续可用
DEEPSEEK_BASE_URL = LLM_BASE_URL
DEEPSEEK_API_KEY = LLM_API_KEY
DEEPSEEK_MODEL = LLM_MODEL

LLM_TEMPERATURE = 0.3
LLM_TOP_P = 0.9
LLM_MAX_TOKENS = 4096

# Redis 配置（会话存储）
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None
SESSION_TTL = 86400 * 7

# MySQL 配置（用户账号存储）
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "rag_engine")

# JWT 配置
# 必须与 Java 端 (rag-engine) 的 jwt.secret 使用同一值，否则 Java 签发的
# 令牌无法在 Python 侧校验。兼容两种变量名：JWT_SECRET（compose/根 .env）
# 与 JWT_SECRET_KEY（backend/.env）。出于安全考虑不再提供内置默认值。
JWT_SECRET_KEY = os.getenv("JWT_SECRET") or os.getenv("JWT_SECRET_KEY") or ""
if len(JWT_SECRET_KEY) < 32:
    raise RuntimeError(
        "JWT 密钥缺失或过短：请在环境变量或 .env 中设置 JWT_SECRET"
        "（需与 Java 端一致，长度至少 32 字符）。"
        "为避免使用弱口令，此处不再提供内置默认值。"
    )
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

# Java 后端配置
JAVA_BACKEND_URL = os.getenv("JAVA_BACKEND_URL", "http://localhost:8002")

# 服务间接口令牌：
# 与 Java 端 rag.internal.token 对应，用于调用 /api/internal/**（不走用户 JWT）。
# 未配置时 Java 会拒绝全部内部请求，因此这里启动即失败，避免出现难以排查的 401。
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "")
if not INTERNAL_API_TOKEN:
    raise RuntimeError(
        "缺少 INTERNAL_API_TOKEN：该令牌用于调用 Java 的 /api/internal/** 服务间接口，"
        "必须与 Java 端 rag.internal.token 一致。请在 .env 中配置。"
    )

# CORS 允许的前端来源（逗号分隔）。不要使用 *：与 allow_credentials=True
# 组合既不合法也不安全，生产环境请改为真实域名。
CORS_ALLOW_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8001,http://127.0.0.1:8001",
    ).split(",")
    if origin.strip()
]

# 服务配置
HOST = os.getenv("HOST", "localhost")
PORT = int(os.getenv("PORT", "8001"))