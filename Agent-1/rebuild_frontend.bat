@echo off
echo Rebuilding React frontend...
cd /d "D:\zhuomian\agent\Agent-1\frontend"
call npx vite build
echo Done! Refresh browser to see changes.
