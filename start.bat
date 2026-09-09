@echo off
chcp 65001 >nul
title RAG Yi Jian Qi Dong

setlocal enabledelayedexpansion

echo ============================================
echo   RAG Zhu Shou - Yi Jian Qi Dong
echo   (Hun He Mo Shi)
echo ============================================
echo.

rem ============================================
rem Check Dependencies
rem ============================================
echo [1/9] Jian Huan Jing Yi Lai...

where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Docker not found. Please install Docker Desktop first.
    pause
    exit /b 1
)
echo   [OK] Docker installed

where java >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Java not found. Please install JDK 21+.
    pause
    exit /b 1
)
echo   [OK] Java installed

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.11+.
    pause
    exit /b 1
)
echo   [OK] Python installed

where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Please install Node.js 18+.
    pause
    exit /b 1
)
echo   [OK] Node.js installed

where mvn >nul 2>nul
if %errorlevel% neq 0 (
    echo [WARN] Maven not found. Will use pre-built JAR if available.
    set USE_PREBUILT_JAR=1
) else (
    echo   [OK] Maven installed
    set USE_PREBUILT_JAR=0
)

echo.

rem ============================================
rem Start Docker Infrastructure
rem ============================================
echo [2/9] Starting Docker Infrastructure (MySQL + Redis + Qdrant)...

docker info >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Docker Desktop is not running.
    pause
    exit /b 1
)

docker compose up -d 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker Compose failed to start.
    pause
    exit /b 1
)
echo   [OK] Docker containers started

rem Wait for MySQL
echo [3/9] Waiting for MySQL...
:wait_mysql
docker exec rag-mysql mysqladmin ping -h localhost -u root -p19980315 >nul 2>nul
if %errorlevel% neq 0 (
    timeout /t 3 /nobreak >nul
    goto wait_mysql
)
echo   [OK] MySQL ready

rem Wait for Redis
echo [4/9] Waiting for Redis...
:wait_redis
docker exec rag-redis redis-cli ping >nul 2>nul
if %errorlevel% neq 0 (
    timeout /t 2 /nobreak >nul
    goto wait_redis
)
echo   [OK] Redis ready

rem Wait for Qdrant
echo [5/9] Waiting for Qdrant...
:wait_qdrant
docker exec rag-qdrant curl -sf http://localhost:6333/health >nul 2>nul
if %errorlevel% neq 0 (
    timeout /t 2 /nobreak >nul
    goto wait_qdrant
)
echo   [OK] Qdrant ready

echo.

rem ============================================
rem Start Java Backend (rag-engine)
rem ============================================
echo [6/9] Starting Java Backend (rag-engine :8002)...

set JAR_PATH=rag-engine\target\rag-engine-1.0.0-SNAPSHOT.jar

if "%USE_PREBUILT_JAR%"=="1" (
    if exist "%JAR_PATH%" (
        echo   [USE] Pre-built JAR found
    ) else (
        echo [ERROR] No JAR found. Please install Maven or build manually.
        echo         Command: cd rag-engine ^&^& mvn package -DskipTests
        pause
        exit /b 1
    )
) else (
    if exist "%JAR_PATH%" (
        echo   [USE] Existing JAR found. Delete target/ to rebuild.
    ) else (
        echo   [BUILD] Building with Maven...
        cd rag-engine
        call mvn package -DskipTests -q
        if !errorlevel! neq 0 (
            echo [ERROR] Maven build failed
            pause
            exit /b 1
        )
        cd ..
        echo   [OK] JAR built
    )
)

set "JAVA_CMD=cd /d %cd% && java -jar rag-engine\target\rag-engine-1.0.0-SNAPSHOT.jar --server.port=8002"
start "rag-engine" cmd /c "%JAVA_CMD%"

echo   [WAIT] Java backend starting (may take 30-60s)...
set attempts=0
:wait_java
timeout /t 3 /nobreak >nul
curl -sf http://localhost:8002/api/health >nul 2>nul
if %errorlevel% neq 0 (
    set /a attempts+=1
    if !attempts! geq 30 (
        echo [WARN] Java backend timeout. Check rag-engine window.
        goto java_continue
    )
    goto wait_java
)
:java_continue
echo   [OK] Java backend started

echo.

rem ============================================
rem Start Python Backend (backend)
rem ============================================
echo [7/9] Starting Python Backend (backend :8001)...

echo   [CHECK] Installing Python dependencies...
cd backend
pip install -r requirements.txt -q 2>&1
cd ..

set "PY_CMD=cd /d %cd%\backend && python main.py"
start "rag-backend" cmd /c "%PY_CMD%"

echo   [WAIT] Python backend starting...
set attempts2=0
:wait_python
timeout /t 2 /nobreak >nul
curl -sf http://localhost:8001/api/health >nul 2>nul
if %errorlevel% neq 0 (
    set /a attempts2+=1
    if !attempts2! geq 20 (
        echo [WARN] Python backend timeout. Check rag-backend window.
        goto python_continue
    )
    goto wait_python
)
:python_continue
echo   [OK] Python backend started

echo.

rem ============================================
rem Register Admin User
rem ============================================
echo [8/9] Registering admin user...

python -c "import urllib.request, json; data=json.dumps({'username':'admin','password':'admin123','display_name':'System Admin'}).encode(); req=urllib.request.Request('http://localhost:8001/api/auth/register',data=data,headers={'Content-Type':'application/json'},method='POST'); resp=urllib.request.urlopen(req,timeout=5); result=json.loads(resp.read()); print('  [OK] Admin registered (admin / admin123)') if result.get('success') or result.get('id') else print('  [INFO] Admin may already exist')" 2>&1

echo.

rem ============================================
rem Start Vue Frontend (rag-admin)
rem ============================================
echo [9/9] Starting Frontend (rag-admin :5173)...

if not exist "rag-admin\node_modules" (
    echo   [INSTALL] Installing frontend dependencies...
    cd rag-admin
    call npm install --silent 2>&1
    cd ..
)

set "VUE_CMD=cd /d %cd%\rag-admin && npm run dev"
start "rag-admin" cmd /c "%VUE_CMD%"

echo   [OK] Frontend started

echo.
echo ============================================
echo   All services started successfully!
echo ============================================
echo.
echo   Access URLs:
echo   -----------------------------------------
echo   Chat UI:       http://localhost:8001
echo   Admin Panel:   http://localhost:5173
echo   -----------------------------------------
echo.
echo   Default account: admin / admin123
echo.
echo   Ports:
echo   MySQL:  3306  |  Redis:  6379  |  Qdrant:  6334
echo   Java:   8002  |  Python: 8001  |  Vue:    5173
echo.
echo   To stop all services, run stop.bat
echo ============================================
echo.

start http://localhost:8001
timeout /t 2 /nobreak >nul
start http://localhost:5173

echo Press any key to close this window...
pause >nul