import traceback
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if path.endswith((".js", ".css", ".html")):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager

from config import HOST, PORT, BASE_DIR
from database.db import init_db, get_redis, close_redis, init_mysql, close_mysql_pool
from middleware.auth_middleware import JWTAuthMiddleware
from routes import chat, knowledge, session, auth, conversation, audit, dashboard, knowledge_bases, chunks, proxy
from agent.route import router as agent_router
from services.session_service import check_redis
# knowledge_base_service 已迁移至 Java 后端
# from services.knowledge_base import knowledge_base_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        await init_mysql()
        print("[INFO] MySQL 初始化完成")
    except Exception as e:
        print(f"[WARNING] MySQL 初始化失败: {e}")
        print("登录功能将不可用，请确保 MySQL 服务已启动")

    try:
        await get_redis()
        await check_redis()
        print("[INFO] Redis 连接成功")
    except Exception as e:
        print(f"[WARNING] Redis 连接失败: {e}")
        print("[INFO] 将使用 SQLite 作为会话存储降级方案")

    try:
        # 模型预加载已迁移至 Java 后端
        # knowledge_base_service.preload()
        print("[INFO] 知识库引擎由 Java 后端管理，Python 前端仅负责 LLM 编排")
    except Exception as e:
        print(f"[WARNING] {e}")

    # 自动扫描已迁移至 Java 后端
    # auto_scan_task = asyncio.create_task(knowledge_base_service.start_auto_scan(interval=10))
    yield
    await close_redis()
    await close_mysql_pool()


app = FastAPI(
    title="企业知识库 RAG 客服助手",
    description="基于 RAG 技术的企业内部知识库智能问答系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(JWTAuthMiddleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": str(exc.detail),
            "type": "HTTPException",
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    messages = [f"{e['loc'][-1] if e['loc'] else ''}: {e['msg']}" for e in errors]
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "; ".join(messages),
            "type": "ValidationError",
            "status_code": 422,
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error": str(exc),
            "type": "ValueError",
            "status_code": 400,
        },
    )


@app.exception_handler(FileNotFoundError)
async def file_not_found_handler(request: Request, exc: FileNotFoundError):
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": str(exc),
            "type": "FileNotFoundError",
            "status_code": 404,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": str(exc),
            "type": type(exc).__name__,
            "status_code": 500,
        },
    )


app.include_router(chat.router)
app.include_router(knowledge.router)
app.include_router(session.router)
app.include_router(auth.router)
app.include_router(conversation.router)
app.include_router(audit.router)
app.include_router(dashboard.router)
app.include_router(knowledge_bases.router)
app.include_router(chunks.router)
app.include_router(agent_router)
app.include_router(proxy.router)


@app.get("/api/health")
async def health_check():
    return JSONResponse(content={"status": "ok", "service": "企业知识库 RAG 客服助手"})


app.mount("/", NoCacheStaticFiles(directory=str(BASE_DIR / "frontend"), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)