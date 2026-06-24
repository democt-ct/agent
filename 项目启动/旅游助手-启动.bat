@echo off
chcp 65001 >nul
setlocal

:: Travel Assistant (Agent-2) - FastAPI :9000 + Worker :8787
title Travel Agent - Startup

set "AGENT_DIR=D:\zhuomian\agent\Agent-2"

if not exist "%AGENT_DIR%" (
    echo [ERROR] Agent-2 not found
    pause
    exit /b 1
)

echo ============================================
echo   travel-agent-worker
echo   FastAPI :9000  ^|  Worker :8787
echo ============================================
echo.

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":9000.*LISTENING" 2^>nul') do (
    echo [WARN] Port 9000 occupied by PID %%a, freeing...
    taskkill /f /pid %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8787.*LISTENING" 2^>nul') do (
    echo [WARN] Port 8787 occupied by PID %%a, freeing...
    taskkill /f /pid %%a >nul 2>&1
)

echo [1/2] Starting FastAPI (port 9000)...
start "" "D:\zhuomian\agent\Agent-2\start_fastapi.bat"

echo [2/2] Starting Worker (port 8787)...
start "" "D:\zhuomian\agent\Agent-2\start_worker.bat"

echo.
echo ============================================
echo   FastAPI : http://127.0.0.1:9000
echo   Worker  : http://127.0.0.1:8787
echo ============================================
echo.
echo Opening browser...
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:9000
pause
endlocal
