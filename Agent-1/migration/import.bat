@echo off
setlocal

set "BACKUP_DIR=%~dp0backups"

set "LATEST_BACKUP=%BACKUP_DIR%\patient_agent.sql"

if not exist "%LATEST_BACKUP%" (
    echo [ERROR] No backup file found!
    echo Please place the .sql file in backups folder.
    pause
    exit /b 1
)

echo ========================================
echo   Import Database
echo ========================================
echo.
echo Backup file: %LATEST_BACKUP%
echo.
echo This will OVERWRITE existing data! (Y/N)
set /p CONFIRM=
if /i not "%CONFIRM%"=="Y" (
    echo Cancelled.
    pause
    exit /b 0
)

echo.
echo Importing...
echo.

docker exec -i patient-agent-postgres psql -U postgres patient_agent < "%LATEST_BACKUP%"

if errorlevel 1 (
    echo [ERROR] Import failed!
    pause
    exit /b 1
)

echo.
echo Import success!
echo.
pause
