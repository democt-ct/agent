@echo off
title Travel-FastAPI
cd /d "D:\zhuomian\agent\Agent-2\fastapi"
D:\zhuomian\agent\Agent-2\.venv\Scripts\uvicorn.exe app:app --app-dir . --host 127.0.0.1 --port 9000 --reload
