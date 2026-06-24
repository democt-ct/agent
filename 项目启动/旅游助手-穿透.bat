@echo off
setlocal enabledelayedexpansion

:: Travel Agent (Agent-2) Public Tunnel
echo ========================================
echo   Travel Agent - Tunnel
echo ========================================
echo.
echo Agent-2 on Cloudflare Workers - local dev tunnel:
echo.

where cloudflared >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   [cloudflared] Run: cloudflared tunnel --url http://127.0.0.1:9000
    set /p START="  Start now? (Y/N): "
    if /i "!START!"=="Y" cloudflared tunnel --url http://127.0.0.1:9000
    goto :end
)

where ngrok >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   [ngrok] Run: ngrok http 9000
    set /p START="  Start now? (Y/N): "
    if /i "!START!"=="Y" ngrok http 9000
    goto :end
)

echo   No tunnel tool found.
echo   Install cloudflared: https://github.com/cloudflare/cloudflared/releases

:end
pause
endlocal
