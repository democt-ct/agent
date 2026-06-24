@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0.."

echo ========================================
echo   Enterprise Multi-Agent - Tunnel Start
echo ========================================
echo.

:: ═══════════════════════════════════════════
:: 1. Find Python
:: ═══════════════════════════════════════════
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
        echo [ERROR] Python not found. Install or activate venv first.
        pause
        exit /b 1
    )
)

:: ═══════════════════════════════════════════
:: 2. Check / install cloudflared
:: ═══════════════════════════════════════════
where cloudflared >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "CF=cloudflared"
) else if exist "%USERPROFILE%\cloudflared.exe" (
    set "CF=%USERPROFILE%\cloudflared.exe"
) else (
    echo [INFO] cloudflared not found, downloading...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile '%USERPROFILE%\cloudflared.exe'"
    if exist "%USERPROFILE%\cloudflared.exe" (
        set "CF=%USERPROFILE%\cloudflared.exe"
        echo [OK] cloudflared installed
    ) else (
        echo [ERROR] Download failed. Manual: https://github.com/cloudflare/cloudflared/releases
        pause
        exit /b 1
    )
)

:: ═══════════════════════════════════════════
:: 3. Choose tunnel mode
:: ═══════════════════════════════════════════
set CF_DIR=%USERPROFILE%\.cloudflared
set CFG=%CF_DIR%\config.yml

if exist "%CFG%" (
    for /f "tokens=2" %%a in ('findstr /c:"hostname:" "%CFG%"') do set HOST=%%a
    if not "%HOST%"=="" goto :run_fixed
)

echo.
echo   Select tunnel mode:
echo     [1] Temp URL  (quick, random *.trycloudflare.com)
echo     [2] Fixed URL (needs Cloudflare account + domain)
echo.
set /p MODE="Enter 1 or 2: "

if "%MODE%"=="2" goto :setup_fixed
goto :run_temp


:: ═══════════════════════════════════════════
:: Temp tunnel
:: ═══════════════════════════════════════════
:run_temp
echo.
echo ===========================================
echo   Mode: Temp Tunnel (trycloudflare.com)
echo ===========================================
echo.

call :start_backend

echo [INFO] Starting tunnel...
echo ===========================================
echo   Public URL will appear below
echo   (https://????.trycloudflare.com)
echo   Press Ctrl+C to stop
echo ===========================================
echo.
"%CF%" tunnel --url http://localhost:8080
goto :cleanup


:: ═══════════════════════════════════════════
:: Setup fixed domain tunnel
:: ═══════════════════════════════════════════
:setup_fixed
echo.
echo ===========================================
echo   Setup Fixed Domain Tunnel
echo ===========================================
echo.

:: Check if already logged in
if exist "%CF_DIR%\cert.pem" (
    echo [STEP 1/4] Already logged in (cert.pem found)
    goto :setup_check_tunnel
)

echo [STEP 1/4] Login to Cloudflare...
"%CF%" tunnel login
if %ERRORLEVEL% NEQ 0 (
    if exist "%CF_DIR%\cert.pem" (
        echo [WARN] Login command failed, but cert.pem exists - continuing
    ) else (
        echo [ERROR] Login failed and no cert.pem found
        pause
        exit /b 1
    )
)

:setup_check_tunnel
echo.
echo [STEP 2/4] Check existing tunnel...

:: Look for existing tunnel credentials
set TUNNEL_NAME=enterprise-agent
set CRED_FILE=
set TUNNEL_ID=
for %%f in ("%CF_DIR%\*.json") do (
    set FN=%%~nxf
    if not "!FN!"=="cert.pem" (
        set CRED_FILE=!FN!
        set TUNNEL_ID=!FN:.json=!
    )
)

if not "%CRED_FILE%"=="" (
    echo [OK] Found existing tunnel credentials: %CRED_FILE%
    echo [OK] Tunnel ID: %TUNNEL_ID%
    goto :setup_domain
)

echo [INFO] No existing tunnel found, creating new one...
"%CF%" tunnel create %TUNNEL_NAME%
if %ERRORLEVEL% NEQ 0 (
    :: Check again - creation might have failed because tunnel already exists remotely
    for %%f in ("%CF_DIR%\*.json") do (
        set FN=%%~nxf
        if not "!FN!"=="cert.pem" set CRED_FILE=!FN!
    )
    if not "%CRED_FILE%"=="" (
        set TUNNEL_ID=%CRED_FILE:.json=%
        echo [OK] Credentials file created: %CRED_FILE%
        echo [OK] Tunnel ID: %TUNNEL_ID%
        goto :setup_domain
    )
    echo [ERROR] Tunnel creation failed
    pause
    exit /b 1
)

:: If creation succeeded, find the new credentials
for %%f in ("%CF_DIR%\*.json") do (
    set FN=%%~nxf
    if not "!FN!"=="cert.pem" set CRED_FILE=!FN!
)
if "%CRED_FILE%"=="" (
    echo [ERROR] Credentials file not found in %CF_DIR%
    pause
    exit /b 1
)
set TUNNEL_ID=%CRED_FILE:.json=%
echo [OK] Tunnel ID: %TUNNEL_ID%

:setup_domain

:: Check if config already has a hostname (previously configured)
if exist "%CFG%" (
    for /f "tokens=2" %%a in ('findstr /c:"hostname:" "%CFG%" 2^>nul') do set EXISTING_HOST=%%a
    if not "%EXISTING_HOST%"=="" (
        echo [INFO] Config already exists with hostname: %EXISTING_HOST%
        echo [INFO] Skipping domain setup, using existing config
        set HOST=%EXISTING_HOST%
        goto :run_fixed
    )
)

echo.
echo [STEP 3/4] Set subdomain...
set /p SUBDOMAIN="Enter subdomain prefix (e.g. nexusai -> nexusai.313070.xyz): "
if "%SUBDOMAIN%"=="" set SUBDOMAIN=nexusai
set HOSTNAME=%SUBDOMAIN%.313070.xyz
echo Domain: %HOSTNAME%

echo.
echo [STEP 4/4] Add DNS + write config...
"%CF%" tunnel route dns %TUNNEL_NAME% %HOSTNAME%
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Auto DNS failed. Add manually:
    echo        Cloudflare Dashboard -^> DNS -^> CNAME
    echo        Name: %SUBDOMAIN%
    echo        Target: %TUNNEL_ID%.cfargotunnel.com
)

:: Write config.yml
echo tunnel: %TUNNEL_ID%> "%CFG%"
echo credentials-file: %CF_DIR%\%CRED_FILE%>> "%CFG%"
echo.>> "%CFG%"
echo ingress:>> "%CFG%"
echo   - hostname: %HOSTNAME%>> "%CFG%"
echo     service: http://localhost:8080>> "%CFG%"
echo   - service: http_status:404>> "%CFG%"
echo [OK] Config saved: %CFG%

set HOST=%HOSTNAME%

echo.
echo ===========================================
echo   Setup complete! Starting...
echo   Public URL: https://%HOSTNAME%
echo ===========================================
echo.

call :start_backend

"%CF%" tunnel --config "%CFG%" run %TUNNEL_NAME%
goto :cleanup


:: ═══════════════════════════════════════════
:: Existing config - run directly
:: ═══════════════════════════════════════════
:run_fixed
echo.
echo ===========================================
echo   Mode: Fixed Domain -^> https://%HOST%
echo ===========================================
echo.

call :start_backend

"%CF%" tunnel --config "%CFG%" run enterprise-agent
goto :cleanup


:: ═══════════════════════════════════════════
:: Sub: start backend
:: ═══════════════════════════════════════════
:start_backend
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080.*LISTENING" 2^>nul') do (
    echo [INFO] Killing old process PID %%a ...
    taskkill /PID %%a /F >nul 2>&1
)

echo [INFO] Starting backend on localhost:8080 ...
start "Agent-Server" /B cmd /c "%PYTHON% -m uvicorn src.api.app:app --host 0.0.0.0 --port 8080"

echo [INFO] Waiting for backend...
:wait_backend
timeout /t 2 /nobreak >nul
curl -s -o nul http://localhost:8080/api/agents 2>nul
if %ERRORLEVEL% NEQ 0 goto :wait_backend
echo [OK] Backend ready

:: Auto-open browser
if "%HOST%"=="" (
    start http://localhost:8080
) else (
    start https://%HOST%
)
exit /b


:: ═══════════════════════════════════════════
:: Cleanup on exit
:: ═══════════════════════════════════════════
:cleanup
taskkill /FI "WINDOWTITLE eq Agent-Server*" /F >nul 2>&1
pause
