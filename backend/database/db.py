import aiosqlite
import aiomysql
import redis.asyncio as aioredis
from config import DB_PATH, REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

_redis_pool = None
_mysql_pool = None


async def get_db():
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    db = await get_db()
    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT DEFAULT '新对话',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                sources TEXT,
                feedback INTEGER DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT DEFAULT '',
                operation TEXT NOT NULL,
                detail TEXT DEFAULT '',
                target_name TEXT DEFAULT '',
                ip_address TEXT DEFAULT '',
                result TEXT DEFAULT 'SUCCESS',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            await db.execute("ALTER TABLE messages ADD COLUMN feedback INTEGER DEFAULT NULL")
        except Exception:
            pass
        await db.commit()
    finally:
        await db.close()


async def get_redis():
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True,
        )
    return _redis_pool


async def close_redis():
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None


async def get_mysql_pool():
    global _mysql_pool
    if _mysql_pool is None:
        _mysql_pool = await aiomysql.create_pool(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            db=MYSQL_DATABASE,
            charset="utf8mb4",
            autocommit=True,
            minsize=1,
            maxsize=10,
        )
    return _mysql_pool


async def close_mysql_pool():
    global _mysql_pool
    if _mysql_pool is not None:
        _mysql_pool.close()
        await _mysql_pool.wait_closed()
        _mysql_pool = None


async def init_mysql():
    pool = await get_mysql_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SHOW TABLES LIKE 'sys_user'")
            if await cur.fetchone():
                print("[INFO] MySQL 表已存在，跳过创建")
                return
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS sys_user (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(32) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    display_name VARCHAR(64) DEFAULT '',
                    email VARCHAR(128) DEFAULT '',
                    phone VARCHAR(20) DEFAULT '',
                    avatar VARCHAR(255) DEFAULT '',
                    status TINYINT DEFAULT 1,
                    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    deleted TINYINT DEFAULT 0
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            print("[INFO] sys_user 表创建完成")