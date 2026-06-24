@echo off
setlocal

:: Agent-3 Enterprise Multi-Agent (port 8080)
set "AGENT_DIR=D:\zhuomian\agent\Agent-3"

if not exist "%AGENT_DIR%\scripts\start_local.bat" (
    echo [ERROR] Agent-3 not found
    pause
    exit /b 1
)

echo [LAUNCH] Agent-3 -^> http://127.0.0.1:8080
cd /d "%AGENT_DIR%"

if not exist ".venv\Scripts\python.exe" (
    if not exist "%USERPROFILE%\.conda\envs\llm\python.exe" (
        echo [WARN] No venv/conda found
    )
)

call scripts\start_local.bat
pause
endlocal
