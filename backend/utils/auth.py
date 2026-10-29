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
    # 角色优先取 JWT claims（登录时写入）；改造前签发的旧 token 没有 roles
    # 声明，回退查库——否则管理台所有 require_admin 写操作对旧会话全部 403。
    # Java 侧 JwtAuthFilter 本就每请求查库，行为保持一致
    roles = payload.get("roles")
    if roles is None:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT r.role_code FROM sys_user_role ur "
                    "JOIN sys_role r ON ur.role_id = r.id WHERE ur.user_id = %s",
                    (user_id,),
                )
                roles = [row[0] for row in await cur.fetchall()]
    user["roles"] = roles or []
    return user