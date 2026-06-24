@echo off
setlocal

:: Agent-1 local start
set "AGENT_DIR=D:\zhuomian\agent\Agent-1"

if not exist "%AGENT_DIR%\start_local.bat" (
    echo [ERROR] start_local.bat not found at %AGENT_DIR%
    pause
    exit /b 1
)

echo [LAUNCH] Agent-1 -^> http://127.0.0.1:8000
cd /d "%AGENT_DIR%"
call start_local.bat
pause
endlocal
