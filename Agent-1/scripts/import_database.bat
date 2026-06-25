@echo off
echo ========================================
echo   数据库导入工具
echo ========================================

set "BACKUP_DIR=%~dp0..\backups"

REM 查找最新的备份文件
set "LATEST_BACKUP="
for /f "delims=" %%i in ('dir /b /o-d "%BACKUP_DIR%\*.sql" 2^>nul') do (
    if not defined LATEST_BACKUP set "LATEST_BACKUP=%BACKUP_DIR%\%%i"
)

if not defined LATEST_BACKUP (
    echo 未找到备份文件！
    echo 请将 .sql 文件放到 backups 文件夹中。
    pause
    exit /b 1
)

echo 找到备份文件: %LATEST_BACKUP%
echo.
echo 确认导入？这将覆盖现有数据！(Y/N)
set /p CONFIRM=
if /i not "%CONFIRM%"=="Y" (
    echo 已取消。
    pause
    exit /b 0
)

echo.
echo 正在导入数据库...
docker exec -i patient-agent-postgres psql -U postgres patient_agent < "%LATEST_BACKUP%"

if errorlevel 1 (
    echo 导入失败！
    pause
    exit /b 1
)

echo.
echo 导入成功！
echo.
pause
