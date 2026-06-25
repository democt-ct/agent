@echo off
echo ========================================
echo   数据库导出工具
echo ========================================

set "BACKUP_DIR=%~dp0..\backups"
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

set "BACKUP_FILE=%BACKUP_DIR%\patient_agent_%date:~0,4%%date:~5,2%%date:~8,2%.sql"

echo 正在导出数据库...
docker exec patient-agent-postgres pg_dump -U postgres patient_agent > "%BACKUP_FILE%"

if errorlevel 1 (
    echo 导出失败！请检查 Docker 是否运行。
    pause
    exit /b 1
)

echo.
echo 导出成功！
echo 文件位置: %BACKUP_FILE%
echo.
echo 在新电脑上运行以下命令导入：
echo docker exec -i patient-agent-postgres psql -U postgres patient_agent ^< "%BACKUP_FILE%"
echo.
pause
