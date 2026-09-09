@echo off
chcp 65001 >nul
title RAG 助手 - 一键启动应用服务 (Redis/Qdrant已手动运行)

echo ============================================
echo   RAG 助手 - 一键启动应用服务
echo ============================================
echo.
echo [INFO] 基础设施服务 (Redis/Qdrant) 已手动启动
echo [INFO] 开始启动应用服务...
echo.

rem 检查 Java
java -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Java 未找到，请安装 JDK 21+ 后重试
    pause
    exit /b 1
)
echo [OK] Java 已安装

rem 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 未找到，请安装 Python 3.11+ 后重试
    pause
    exit /b 1
)
echo [OK] Python 已安装

rem 检查 Node.js
node -v >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js 未找到，请安装 Node.js 18+ 后重试
    pause
    exit /b 1
)
echo [OK] Node.js 已安装

rem 检查 JAR 文件
if not exist "rag-engine\target\rag-engine-1.0.0-SNAPSHOT.jar" (
    echo [ERROR] rag-engine-1.0.0-SNAPSHOT.jar 不存在，请先执行 Maven 构建
    echo        cd rag-engine ^&^& mvn clean package
    pause
    exit /b 1
)
echo [OK] Java JAR 包已就绪

echo.
echo ============================================
echo   启动 Java 后端 (rag-engine, 端口 8002)
echo ============================================
echo.
start "rag-engine (Java 后端 - 端口 8002)" cmd /k "java -jar rag-engine\target\rag-engine-1.0.0-SNAPSHOT.jar --server.port=8002"

echo [INFO] 等待 Java 后端启动...
timeout /t 15 /nobreak >nul

echo.
echo ============================================
echo   启动 Python 后端 (backend, 端口 8001)
echo ============================================
echo.
cd backend
start "rag-backend (Python 后端 - 端口 8001)" cmd /k "python main.py"

echo [INFO] 等待 Python 后端启动...
timeout /t 10 /nobreak >nul

cd ..

echo.
echo ============================================
echo   启动 Vue 前端 (rag-admin, 端口 5173)
echo ============================================
echo.
cd rag-admin
start "rag-admin (Vue 前端 - 端口 5173)" cmd /k "npm run dev"

echo [INFO] 等待前端启动...
timeout /t 10 /nobreak >nul

cd ..

echo.
echo ============================================
echo   所有服务已启动！
echo ============================================
echo.
echo 访问地址:
echo   - 前端管理界面: http://localhost:5173
echo   - Python API:   http://localhost:8001
echo   - Java API:      http://localhost:8002
echo.
echo 默认管理员账号:
echo   用户名: admin
echo   密码:   admin123
echo.
echo 提示: 各个服务已在独立窗口中运行，关闭窗口即可停止对应服务
echo.

start http://localhost:5173