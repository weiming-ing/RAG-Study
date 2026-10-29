import os
import threading
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

from config import HOST, PORT, BASE_DIR, CORS_ALLOW_ORIGINS
from database.db import init_db, get_redis, close_redis, init_mysql, close_mysql_pool
from middleware.auth_middleware import JWTAuthMiddleware
from middleware.license_middleware import LicenseMiddleware
from middleware.rate_limit_middleware import RateLimitMiddleware
from routes import chat, knowledge, session, auth, conversation, audit, dashboard, knowledge_bases, chunks, proxy, kb_browse
from routes import license as license_routes
from agent.route import router as agent_router
from services import session_service as session_svc
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
        if session_svc.REDIS_AVAILABLE:
            print("[INFO] Redis 连接成功")
        else:
            # 必须如实告警：降级模式下游会话走 SQLite、语义缓存与限流失效
            print(f"[ERROR] Redis 连接失败: {session_svc.REDIS_ERROR}")
            print("[ERROR] 已降级：会话走 SQLite，语义缓存与限流不生效。请检查 Redis 服务与 REDIS_PASSWORD 配置")
    except Exception as e:
        print(f"[ERROR] Redis 初始化异常: {e}")

    try:
        # 模型预加载已迁移至 Java 后端
        # knowledge_base_service.preload()
        print("[INFO] 知识库引擎由 Java 后端管理，Python 前端仅负责 LLM 编排")
    except Exception as e:
        print(f"[WARNING] {e}")

    # 在后台线程中预初始化 Docling 解析器，避免阻塞首次上传请求
    try:
        from services.docling_service import docling_service
        init_thread = threading.Thread(target=docling_service.init_background, daemon=True)
        init_thread.start()
        print("[INFO] Docling 解析器后台初始化中...")
    except Exception as e:
        print(f"[WARNING] Docling 初始化启动失败: {e}")

    # 自动扫描已迁移至 Java 后端
    # auto_scan_task = asyncio.create_task(knowledge_base_service.start_auto_scan(interval=10))
    yield
    from utils.java_http import aclose as close_java_http
    await close_java_http()
    await close_redis()
    await close_mysql_pool()


app = FastAPI(
    title="企业知识库 RAG 客服助手",
    description="基于 RAG 技术的企业内部知识库智能问答系统",
    version="1.0.0",
    lifespan=lifespan,
)

# 不再使用通配来源：allow_origins=["*"] 与 allow_credentials=True 组合
# 既不合法也不安全。允许的来源由 CORS_ALLOW_ORIGINS 环境变量配置。
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注意中间件顺序：先添加的更靠内层、更后执行（构建时反序包裹）。
# 限流最先添加（最内层）：在 JWT 之后执行，可读取 request.state.user
# 按用户计数，未登录请求按 client IP 计数。
# 授权校验在 JWT 之外层先执行，使未登录请求先被 401 拦下，
# 不会把授权状态泄露给匿名调用者。
app.add_middleware(RateLimitMiddleware)
app.add_middleware(LicenseMiddleware)
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
app.include_router(kb_browse.router)
app.include_router(session.router)
app.include_router(auth.router)
app.include_router(conversation.router)
app.include_router(audit.router)
app.include_router(dashboard.router)
app.include_router(knowledge_bases.router)
app.include_router(chunks.router)
app.include_router(agent_router)
app.include_router(proxy.router)
app.include_router(license_routes.router)


@app.get("/api/health")
async def health_check():
    from services.docling_service import docling_service
    return JSONResponse(content={
        "status": "ok",
        "service": "企业知识库 RAG 客服助手",
        "redis": {"available": session_svc.REDIS_AVAILABLE, "error": session_svc.REDIS_ERROR},
        "docling": {
            "ready": docling_service.ready,
            "initialized": docling_service._initialized,
            "error": docling_service._init_error,
        }
    })


app.mount("/", NoCacheStaticFiles(directory=str(BASE_DIR / "frontend"), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    # 生产模式：通过环境变量 UVICORN_RELOAD=true 开发热重载。
    # 默认关闭：reload 模式的文件监听会孤儿化 worker（杀父进程不杀子进程），
    # 多人开发机上曾出现多个进程抢占同一端口的事故。
    use_reload = os.getenv("UVICORN_RELOAD", "false").lower() == "true"
    # 生产模式默认使用多 worker（单实例时），多实例场景每个实例 1 个 worker
    workers = int(os.getenv("UVICORN_WORKERS", "1"))

    log_level = os.getenv("UVICORN_LOG_LEVEL", "info")

    print(f"[启动] 模式={'开发' if use_reload else '生产'}, "
          f"Host={HOST}, Port={PORT}, Workers={workers}")

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=use_reload,
        workers=workers if not use_reload else 1,
        log_level=log_level,
        access_log=True,
    )