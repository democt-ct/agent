@echo off
setlocal

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

set "PYTHON=python"
if exist "%ROOT%\.venv\Scripts\python.exe" set "PYTHON=%ROOT%\.venv\Scripts\python.exe"

echo ========================================
echo   Agent-1 - Tunnel Start
echo ========================================
echo.

echo [1/4] Docker + Containers...
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

echo [2/4] PostgreSQL...
"%PYTHON%" -c "import psycopg2; psycopg2.connect(host='localhost',port=5432,user='postgres',password='postgres',dbname='patient_agent',connect_timeout=5).close(); print('OK')" 2>nul | findstr "OK" >nul
if errorlevel 1 (
    echo [ERROR] PostgreSQL not ready.
    pause
    exit /b 1
)

echo [3/4] Starting backend...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING" 2^>nul') do taskkill /f /pid %%a >nul 2>&1

set "LOG=%TEMP%\uvicorn_agent.log"
start "Agent-1 Backend" /min cmd /c ""%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > "%LOG%" 2>&1"

timeout /t 3 /nobreak >nul
curl -s -o nul http://127.0.0.1:8000/ 2>nul
if errorlevel 1 (
    echo [ERROR] Backend not responding. See %LOG%
    pause
    exit /b 1
)

echo [4/4] Tunnel...
set "CF=D:\zhuomian\cloudflared-windows-amd64.exe"
where cloudflared >nul 2>&1 && set "CF=cloudflared"
if not exist "%CF%" powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile '%CF%'"
if not exist "%CF%" (
    echo [ERROR] cloudflared not found.
    pause
    exit /b 1
)

set "CFG=%ROOT%\.cloudflared\config.yml"
if exist "%CFG%" (
    echo Named tunnel: agent.313070.xyz
    "%CF%" --config "%CFG%" tunnel --protocol http2 run agent-1
) else (
    echo Quick tunnel: temporary URL below.
    "%CF%" tunnel --protocol http2 --url http://127.0.0.1:8000
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING" 2^>nul') do taskkill /f /pid %%a >nul 2>&1
pause
endlocal
