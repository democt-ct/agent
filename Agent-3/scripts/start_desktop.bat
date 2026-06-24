@echo off
cd /d "D:\zhuomian\agent\Agent-3"

echo ========================================
echo   企业多专家 Agent 系统 - 启动
echo ========================================
echo.

:: ── 1. Find Python ─────────────────────────
set PYTHON=
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
    echo [INFO] Using .venv
) else if exist "%USERPROFILE%\.conda\envs\llm\python.exe" (
    set "PYTHON=%USERPROFILE%\.conda\envs\llm\python.exe"
    echo [INFO] Using conda env llm
) else (
    where python >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set "PYTHON=python"
        echo [INFO] Using system Python
    ) else (
        echo [ERROR] Python not found. Please install or activate venv.
        pause
        exit /b 1
    )
)

:: ── 2. Kill old process on port 8080 ───────
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080.*LISTENING" 2^>nul') do (
    echo [INFO] Killing old process PID %%a ...
    taskkill /PID %%a /F >nul 2>&1
)

:: ── 3. Start backend ───────────────────────
echo.
echo [INFO] Starting backend on http://127.0.0.1:8080 ...

start "" /B %PYTHON% -m uvicorn src.api.app:app --host 0.0.0.0 --port 8080

:: Wait until backend actually responds
echo [INFO] Waiting for backend to be ready...
:wait_backend
timeout /t 2 /nobreak >nul
curl -s -o nul http://localhost:8080/api/agents 2>nul
if %ERRORLEVEL% NEQ 0 goto :wait_backend

echo [OK] Backend ready, opening browser...
start "" http://127.0.0.1:8080

echo.
echo ===========================================
echo   Backend is running. Press Ctrl+C to stop.
echo ===========================================
:loop
timeout /t 10 /nobreak >nul
goto :loop
