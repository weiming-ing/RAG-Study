# ---- Build Stage ----
# vite 8 要求 Node ^20.19 || >=22.12，用 node:22
FROM node:22-alpine AS build

WORKDIR /app

# 先复制依赖文件利用缓存
COPY package.json package-lock.json* ./
RUN npm ci --registry=https://registry.npmmirror.com

# 复制源码并构建（vite base = /admin/，见 vite.config.js）
COPY . .
RUN npm run build

# ---- Serve Stage ----
FROM nginx:alpine

# 管理台 -> /admin/
COPY --from=build /app/dist /usr/share/nginx/html/admin

# 员工聊天页 -> 根路径
# 来自 docker-compose.yml 的 additional_contexts（chatui: ./frontend）
COPY --from=chatui . /usr/share/nginx/html

# 复制 nginx 配置（统一入口：/ 聊天页，/admin/ 管理台，/api/ 后端）
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# 用 /health 而不是 /：不依赖静态文件是否存在，容器健康状态更可信
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:80/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
