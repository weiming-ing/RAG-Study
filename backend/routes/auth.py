from datetime import datetime, timedelta
import os
import httpx
import aiomysql
import bcrypt
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from models.schemas import UserLogin, UserRegister
from database.db import get_mysql_pool
from config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_MINUTES
from utils.auth import decode_token_and_get_user
from utils.internal_api import internal_headers

JAVA_BACKEND = os.getenv("JAVA_BACKEND_URL", "http://localhost:8002")

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode()[:72], hashed.encode())


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        return await decode_token_and_get_user(credentials.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="无效的认证令牌")
    except ValueError:
        raise HTTPException(status_code=401, detail="用户不存在")


@router.post("/register", response_model=dict)
async def register(body: UserRegister):
    pool = await get_mysql_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM sys_user WHERE username = %s", (body.username,))
            if await cur.fetchone():
                raise HTTPException(status_code=400, detail="用户名已存在")

    password_hash = hash_password(body.password)
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO sys_user (username, password, display_name) VALUES (%s, %s, %s)",
                (body.username, password_hash, body.display_name or body.username),
            )

    await _record_audit(body.username, "REGISTER", "注册成功")

    return {"success": True, "message": "注册成功"}


async def _get_user_roles(user_id: int) -> list:
    """查询用户角色码（sys_user_role → sys_role），无角色返回空表。"""
    pool = await get_mysql_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT r.role_code FROM sys_user_role ur "
                "JOIN sys_role r ON ur.role_id = r.id WHERE ur.user_id = %s",
                (user_id,),
            )
            return [row[0] for row in await cur.fetchall()]


# 管理台准入与管理写操作的最低角色集：管理员全权，知识库管理员管内容
ADMIN_ROLES = ("ROLE_ADMIN", "ROLE_KB_ADMIN")


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """管理写操作的角色门禁。

    Java 侧 /api/admin/** 由 @PreAuthorize 兜底，但 KB/文档/分块的写接口
    在 Java 侧是 internal 接口（无用户级鉴权），Python 这里是唯一防线。
    角色取自 JWT claims（登录时写入），改角色需重新登录生效。
    """
    roles = current_user.get("roles") or []
    if not any(r in ADMIN_ROLES for r in roles):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


async def get_user_or_api_key(request: Request) -> dict:
    """对话入口双轨鉴权：Authorization Bearer JWT 优先；否则 X-API-Key。

    API Key 供外部系统调用开放 API：JWTAuthMiddleware 已完成校验并写入
    request.state.user，这里直接复用，避免重复调用 Java 计数接口。
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        try:
            return await decode_token_and_get_user(auth_header.replace("Bearer ", ""))
        except JWTError:
            raise HTTPException(status_code=401, detail="无效的认证令牌")
        except ValueError:
            raise HTTPException(status_code=401, detail="用户不存在")
    state_user = getattr(request.state, "user", None)
    if state_user is not None and state_user.get("via_api_key"):
        return state_user
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        from utils.api_key_auth import resolve_api_key_user
        api_user = await resolve_api_key_user(api_key)
        if api_user is None:
            raise HTTPException(status_code=401, detail="无效或已禁用的 API Key")
        return api_user
    raise HTTPException(status_code=401, detail="未提供认证凭据")


@router.post("/login", response_model=dict)
async def login(body: UserLogin):
    pool = await get_mysql_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, username, password, display_name FROM sys_user WHERE username = %s",
                (body.username,),
            )
            user = await cur.fetchone()

    if not user:
        await _record_audit(body.username, "LOGIN", "登录失败：用户不存在", result="FAIL")
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not verify_password(body.password, user["password"]):
        await _record_audit(body.username, "LOGIN", "登录失败：密码错误", result="FAIL")
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    roles = await _get_user_roles(user["id"])

    access_token = create_access_token(
        data={"user_id": user["id"], "userId": user["id"], "username": user["username"], "sub": user["username"], "roles": roles}
    )

    await _record_audit(body.username, "LOGIN", "登录成功", user_id=user["id"])

    return {
        "success": True,
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "username": user["username"],
            "display_name": user["display_name"],
            "roles": roles,
        },
    }


async def _record_audit(username: str, operation: str, detail: str, target_name: str = "", ip_address: str = "", result: str = "SUCCESS", user_id: int = None):
    try:
        body = {
            "username": username,
            "operation": operation,
            "detail": detail,
            "targetName": target_name,
            "ipAddress": ip_address,
            "result": result,
        }
        if user_id is not None:
            body["userId"] = user_id
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{JAVA_BACKEND}/api/audit-logs",
                json=body,
            )
    except Exception:
        pass


@router.get("/me", response_model=dict)
async def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "success": True,
        "data": {
            "id": current_user["id"],
            "username": current_user["username"],
            "display_name": current_user["display_name"],
            "roles": current_user.get("roles") or [],
            "create_time": current_user["create_time"].isoformat() if hasattr(current_user["create_time"], "isoformat") else str(current_user["create_time"]),
        },
    }