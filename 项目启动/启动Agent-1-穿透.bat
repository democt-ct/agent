@echo off
setlocal

:: Agent-1 tunnel start
set "AGENT_DIR=D:\zhuomian\agent\Agent-1"

if not exist "%AGENT_DIR%\start_tunnel.bat" (
    echo [ERROR] start_tunnel.bat not found at %AGENT_DIR%
    pause
    exit /b 1
)

echo [LAUNCH] Agent-1 + Tunnel
cd /d "%AGENT_DIR%"
call start_tunnel.bat
pause
endlocal
