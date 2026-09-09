@echo off
chcp 65001 >nul
title RAG Stop

echo ============================================
echo   Stopping all services...
echo ============================================
echo.

echo [1/3] Stopping application processes...

taskkill /f /fi "WINDOWTITLE eq rag-admin" /t >nul 2>nul
echo   Stopped: rag-admin (Vue frontend)

taskkill /f /fi "WINDOWTITLE eq rag-backend" /t >nul 2>nul
echo   Stopped: rag-backend (Python backend)

taskkill /f /fi "WINDOWTITLE eq rag-engine" /t >nul 2>nul
echo   Stopped: rag-engine (Java backend)

echo.

echo [2/3] Stopping Docker containers...

docker compose down 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Docker containers stopped
) else (
    echo   [WARN] Force stopping containers...
    docker stop rag-mysql rag-redis rag-qdrant >nul 2>nul
    docker rm rag-mysql rag-redis rag-qdrant >nul 2>nul
    echo   [OK] Containers force stopped
)

echo.

echo [3/3] Cleaning up remaining processes...

taskkill /f /im java.exe >nul 2>nul
taskkill /f /im python.exe >nul 2>nul
taskkill /f /im node.exe >nul 2>nul
echo   [OK] Cleanup done

echo.
echo ============================================
echo   All services stopped.
echo   Docker data volumes preserved.
echo ============================================
echo.
echo   To also remove data volumes, run:
echo   docker compose down -v
echo.
echo   To restart, run start.bat
echo ============================================
echo.

pause