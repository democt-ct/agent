@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

set "PYTHON=python"
if exist "%ROOT%\.venv\Scripts\python.exe" set "PYTHON=%ROOT%\.venv\Scripts\python.exe"

set HF_ENDPOINT=https://hf-mirror.com

echo ========================================
echo   Agent-1 - Local Dev Start
echo ========================================
echo.

echo [1/3] Docker + Containers...
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker not running.
    pause
    exit /b 1
)

cd /d "%ROOT%"
docker compose up -d >nul 2>&1
if errorlevel 1 (
    docker-compose up -d >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] docker-compose failed.
        pause
        exit /b 1
    )
)

echo [2/3] PostgreSQL...
set "RETRIES=20"
:pg_wait
powershell -NoProfile -Command "try { $t = New-Object Net.Sockets.TcpClient; $t.Connect('localhost',5433); $t.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto pg_ok
set /a RETRIES-=1
if !RETRIES! leq 0 (
    echo [ERROR] PostgreSQL not ready.
    pause
    exit /b 1
)
timeout /t 1 >nul
goto pg_wait
:pg_ok

echo [3/3] Starting services...
echo   - Killing leftover processes on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R ":8000.*LISTENING" 2^>nul') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R ":3000.*LISTENING" 2^>nul') do taskkill /f /pid %%a >nul 2>&1
echo   - Killing leftover uvicorn/python processes...
taskkill /f /im uvicorn.exe >nul 2>&1
for /f "tokens=2" %%a in ('wmic process where "commandline like '%%uvicorn%%app.main%%'" get processid /value 2^>nul ^| findstr ProcessId') do taskkill /f /pid %%a >nul 2>&1
timeout /t 1 >nul

set "BLOG=%TEMP%\agent1_backend.log"

REM 清除旧日志文件，避免文件锁冲突
del /f /q "%BLOG%" >nul 2>&1
timeout /t 1 >nul

start /b "" cmd /c "cd /d "%ROOT%" && "%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload > "%BLOG%" 2>&1"

echo Waiting for backend...
set "BRETRIES=20"
:wait_backend
curl -s -o nul http://127.0.0.1:8000/health 2>nul
if not errorlevel 1 goto backend_ok
set /a BRETRIES-=1
if !BRETRIES! leq 0 (
    echo [ERROR] Backend not responding. Log: %BLOG%
    pause
    exit /b 1
)
timeout /t 1 >nul
goto wait_backend
:backend_ok

start http://localhost:3000
echo.
echo ========================================
echo   http://localhost:3000  ^(Ctrl+C to stop^)
echo   Backend log: %BLOG%
echo ========================================
echo.

cd /d "%ROOT%\frontend"
call npm run dev

pause
endlocal
