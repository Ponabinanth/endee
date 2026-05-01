@echo off
setlocal
set ROOT=%~dp0
start "" /min /D "%ROOT%backend" cmd /c "python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 > ..\backend.dev.out.log 2> ..\backend.dev.err.log"
start "" /min /D "%ROOT%frontend" cmd /c "node node_modules\vite\bin\vite.js --host 127.0.0.1 --port 5173 > ..\frontend.dev.out.log 2> ..\frontend.dev.err.log"
endlocal
