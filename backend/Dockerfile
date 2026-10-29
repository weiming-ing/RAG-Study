FROM python:3.11-slim

WORKDIR /app

# 是否安装可选的本地降级检索依赖（chromadb + sentence-transformers/torch）。
# 默认 false：容器部署下该路径不可用，且会让镜像膨胀数 GB。
# 需要时：docker compose build --build-arg INSTALL_FALLBACK=true backend
ARG INSTALL_FALLBACK=false

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖清单并安装（requirements-fallback.txt 仅在开关打开时使用）
COPY requirements.txt requirements-fallback.txt ./
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && if [ "$INSTALL_FALLBACK" = "true" ]; then \
         echo ">>> 安装可选的本地降级检索依赖（体积较大）" && \
         pip install --no-cache-dir -r requirements-fallback.txt -i https://pypi.tuna.tsinghua.edu.cn/simple; \
       fi

# 复制应用代码（.env / data / __pycache__ 等由 .dockerignore 排除）
COPY . .

# 数据目录（通过环境变量指向，确保与卷挂载一致）
ENV DATA_DIR=/app/data
RUN mkdir -p /app/data/documents /app/data/chroma_db

# 容器内 BASE_DIR 为 /（本地开发时是仓库根）。main.py 末尾会挂载
# BASE_DIR/frontend 静态目录，这里补一个空目录避免启动报错——
# 容器部署下聊天页由前端镜像的 Nginx 统一提供，此目录仅为兜底。
RUN mkdir -p /frontend

EXPOSE 8001

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8001/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
