@echo off
setlocal

:: Agent-3 Enterprise Multi-Agent Tunnel (nexusai.313070.xyz)
set "AGENT_DIR=D:\zhuomian\agent\Agent-3"

if not exist "%AGENT_DIR%\scripts\start_tunnel.bat" (
    echo [ERROR] Agent-3 tunnel script not found
    pause
    exit /b 1
)

echo [LAUNCH] Agent-3 + Tunnel -^> https://nexusai.313070.xyz
cd /d "%AGENT_DIR%"
call scripts\start_tunnel.bat
pause
endlocal
