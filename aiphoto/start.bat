@echo off
title AI Photo Agent
set ROOT=%~dp0

:: -- Docker --
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Starting Docker Desktop...
    start "" "C:\Users\31307\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe"
    for /l %%i in (1,1,30) do (
        timeout /t 2 /nobreak >nul
        docker info >nul 2>&1
        if not errorlevel 1 goto :docker_ok
    )
    echo [FAIL] Docker failed to start & pause & exit /b 1
)
:docker_ok

:: -- Skip containers if already running --
docker ps --format "{{.Names}}" | findstr /c:"aiphoto-postgres" >nul 2>&1
if %errorlevel% neq 0 (
    echo Starting containers...
    cd /d "%ROOT%" && docker compose up -d
    for /l %%i in (1,1,15) do (
        timeout /t 1 /nobreak >nul
        docker exec aiphoto-postgres pg_isready -U aiphoto >nul 2>&1
        if not errorlevel 1 goto :db_ok
    )
)
:db_ok

:: -- Backend + Frontend --
start "Backend"  cmd /c "cd /d "%ROOT%backend"  && uvicorn app.main:app --reload --host 0.0.0.0 --port 8011"
start "Frontend" cmd /c "cd /d "%ROOT%frontend" && npm run dev"

echo Waiting for frontend to start...
timeout /t 8 /nobreak >nul
start "" "http://localhost:3000"

echo.
echo  Frontend : http://localhost:3000
echo  API Docs : http://localhost:8011/docs
echo.
pause
