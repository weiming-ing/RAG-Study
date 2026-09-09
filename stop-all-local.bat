@echo off
chcp 65001 >nul
title RAG Stop

echo ============================================
echo   Stopping all local services...
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

echo [2/3] Stopping infrastructure services...

taskkill /f /fi "WINDOWTITLE eq mysql" /t >nul 2>nul
echo   Stopped: MySQL

taskkill /f /fi "WINDOWTITLE eq redis" /t >nul 2>nul
echo   Stopped: Redis

taskkill /f /fi "WINDOWTITLE eq qdrant" /t >nul 2>nul
echo   Stopped: Qdrant

echo.

echo [3/3] Cleaning up remaining processes...

taskkill /f /im java.exe >nul 2>nul
taskkill /f /im python.exe >nul 2>nul
taskkill /f /im node.exe >nul 2>nul

echo   [OK] Cleanup done

echo.
echo ============================================
echo   All services stopped.
echo   To restart, run start-all-local.bat
echo ============================================
echo.

pause