import aiomysql
from jose import jwt, JWTError
from database.db import get_mysql_pool
from config import JWT_SECRET_KEY, JWT_ALGORITHM


async def decode_token_and_get_user(token: str) -> dict:
    """解码 JWT token 并查询 MySQL 获取用户信息，失败时抛出异常"""
    payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    user_id: int = payload.get("user_id")
    username: str = payload.get("username")
    if user_id is None or username is None:
        raise JWTError("无效的令牌载荷")

    pool = await get_mysql_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, username, display_name, create_time FROM sys_user WHERE id = %s",
                (user_id,),
            )
            user = await cur.fetchone()
            if not user:
                raise ValueError("用户不存在")
    return user