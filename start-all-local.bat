@echo off
chcp 65001 >nul
title RAG Local

echo ============================================
echo   RAG One-Click Start (Local Mode)
echo ============================================
echo.

echo [1/6] Check dependencies...

where java >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Java not found. Need JDK 21+.
    pause
    exit /b 1
)
echo   [OK] Java found

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Need Python 3.11+.
    pause
    exit /b 1
)
echo   [OK] Python found

where node >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js not found. Need Node.js 18+.
    pause
    exit /b 1
)
echo   [OK] Node.js found

where mvn >nul 2>nul
if errorlevel 1 (
    echo [WARN] Maven not found. Will use pre-built JAR.
    set USE_PREBUILT=1
) else (
    echo   [OK] Maven found
    set USE_PREBUILT=0
)

echo.

echo [2/6] Build Java backend...

set JAR=rag-engine\target\rag-engine-1.0.0-SNAPSHOT.jar

if "%USE_PREBUILT%"=="1" (
    if not exist "%JAR%" (
        echo [ERROR] No JAR found. Install Maven or build manually.
        pause
        exit /b 1
    )
    echo   [OK] Using pre-built JAR
) else (
    if exist "%JAR%" (
        echo   [OK] Using existing JAR
    ) else (
        echo   Building with Maven...
        cd rag-engine
        call mvn package -DskipTests -q
        if errorlevel 1 (
            echo [ERROR] Maven build failed
            pause
            exit /b 1
        )
        cd ..
        echo   [OK] Build complete
    )
)

echo.

echo [3/6] Start Java backend (port 8002)...
start "rag-engine" cmd /c "java -jar %JAR% --server.port=8002"
echo   Waiting for Java backend...
set attempts=0
:wait_java
timeout /t 3 /nobreak >nul
curl -sf http://localhost:8002/api/health >nul 2>nul
if errorlevel 1 (
    set /a attempts+=1
    if !attempts! geq 30 (
        echo [WARN] Java backend timeout. Check rag-engine window.
        goto java_done
    )
    goto wait_java
)
:java_done
echo   [OK] Java backend ready

echo.

echo [4/6] Install Python dependencies and start backend (port 8001)...
cd backend
pip install -r requirements.txt -q 2>&1
cd ..

start "rag-backend" cmd /c "python backend/main.py"
echo   Waiting for Python backend...
set attempts2=0
:wait_python
timeout /t 2 /nobreak >nul
curl -sf http://localhost:8001/api/health >nul 2>nul
if errorlevel 1 (
    set /a attempts2+=1
    if !attempts2! geq 20 (
        echo [WARN] Python backend timeout. Check rag-backend window.
        goto python_done
    )
    goto wait_python
)
:python_done
echo   [OK] Python backend ready

echo.

echo [5/6] Register admin user...
python -c "import urllib.request,json;d=json.dumps({'username':'admin','password':'admin123','display_name':'Admin'}).encode();r=urllib.request.Request('http://localhost:8001/api/auth/register',data=d,headers={'Content-Type':'application/json'},method='POST');urllib.request.urlopen(r,timeout=5);print('  [OK] Admin registered (admin/admin123)')" 2>nul
if errorlevel 1 (
    echo   [INFO] Admin may already exist, skipping
)

echo.

echo [6/6] Start Vue frontend (port 5173)...
if not exist "rag-admin\node_modules" (
    echo   Installing frontend dependencies...
    cd rag-admin
    call npm install --silent 2>&1
    cd ..
)
start "rag-admin" cmd /c "cd rag-admin && npm run dev"
echo   [OK] Frontend started

echo.
echo ============================================
echo   All services started!
echo ============================================
echo.
echo   Chat UI:      http://localhost:8001
echo   Admin Panel:  http://localhost:5173
echo   Account:      admin / admin123
echo ============================================
echo.

start http://localhost:8001
timeout /t 1 /nobreak >nul
start http://localhost:5173

echo Press any key to close this window...
pause >nul