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

    access_token = create_access_token(
        data={"user_id": user["id"], "userId": user["id"], "username": user["username"], "sub": user["username"]}
    )

    await _record_audit(body.username, "LOGIN", "登录成功", user_id=user["id"])

    return {
        "success": True,
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "username": user["username"],
            "display_name": user["display_name"],
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
            "create_time": current_user["create_time"].isoformat() if hasattr(current_user["create_time"], "isoformat") else str(current_user["create_time"]),
        },
    }