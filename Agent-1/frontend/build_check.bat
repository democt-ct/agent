@echo off
cd /d D:\zhuomian\agent\Agent-1\frontend
echo === Running vite build ===
npx vite build
echo === Build exit code: %ERRORLEVEL% ===
echo === Checking dist\assets ===
if exist "dist\assets" (
    echo dist\assets EXISTS
    dir dist\assets /b
) else (
    echo dist\assets DOES NOT EXIST
    dir dist /b 2>nul || echo dist folder does not exist either
)
