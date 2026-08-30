import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# 数据目录
DATA_DIR = BASE_DIR / "data"
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

# Agent 模式配置
ENABLE_AGENT_MODE = True
AGENT_MAX_ITERATIONS = 5
AGENT_CONFIDENCE_THRESHOLD = 0.3

# 检索配置
TOP_K = int(os.getenv("TOP_K", "5"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.3"))
USE_HYBRID_SEARCH = os.getenv("USE_HYBRID_SEARCH", "true").lower() == "true"
VECTOR_WEIGHT = float(os.getenv("VECTOR_WEIGHT", "0.7"))
BM25_WEIGHT = float(os.getenv("BM25_WEIGHT", "0.3"))

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
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
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS512")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

# Java 后端配置
JAVA_BACKEND_URL = os.getenv("JAVA_BACKEND_URL", "http://localhost:8002")

# 服务配置
HOST = os.getenv("HOST", "localhost")
PORT = int(os.getenv("PORT", "8001"))