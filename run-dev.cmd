@echo off
setlocal

REM Run the FastAPI dashboard locally (Windows).
REM Logs go to uvicorn.detached.out.log / uvicorn.detached.err.log in the repo root.

cd /d "%~dp0"

".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info 1> uvicorn.detached.out.log 2> uvicorn.detached.err.log

