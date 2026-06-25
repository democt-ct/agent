@echo off
setlocal

set "ROOT=%~dp0.."
set "BACKUP_DIR=%~dp0backups"
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

set "BACKUP_FILE=%BACKUP_DIR%\patient_agent.sql"

echo ========================================
echo   Export Database
echo ========================================
echo.

docker exec patient-agent-postgres pg_dump -U postgres patient_agent > "%BACKUP_FILE%"

if errorlevel 1 (
    echo [ERROR] Export failed!
    echo Please check if Docker is running.
    pause
    exit /b 1
)

echo.
echo Export success!
echo File: %BACKUP_FILE%
echo.
pause
