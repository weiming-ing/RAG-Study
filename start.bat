@echo off
chcp 65001 >nul
echo.
echo ============================================
echo   RAG 助手 - Docker 容器化启动脚本
echo ============================================
echo.

REM 检查 .env 文件
if not exist ".env" (
    echo [WARNING] 未找到 .env 文件，将使用 docker\.env 作为默认配置
    copy docker\.env .env >nul
    echo [INFO] 已从 docker\.env 复制默认配置
)

echo [1/3] 构建 Docker 镜像...
docker-compose build

echo.
echo [2/3] 启动所有服务...
docker-compose up -d

echo.
echo [3/3] 等待服务就绪...
echo   - 等待 MySQL 就绪...
timeout /t 10 /nobreak >nul

echo.
echo ============================================
echo   ✓ 启动完成！访问地址：
echo.
echo   前端:  http://localhost:80
echo   Python API: http://localhost:8001
echo   Java API:   http://localhost:8002
echo.
echo   默认管理员: admin / admin123
echo ============================================
echo.
echo 常用命令:
echo   查看日志: docker-compose logs -f
echo   停止服务: docker-compose down
echo   重启服务: docker-compose restart
echo   查看状态: docker-compose ps
echo.
pause