@echo off
echo Starting SmartBank...
title SmartBank Server

cd /d "%~dp0"

REM Install frontend dependencies if needed
if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    cd frontend
    call npm install
    call npm run build
    cd ..
)

echo.
echo Starting backend on http://localhost:8000
echo Frontend: http://localhost:8000/app/login.html
echo.
echo Press Ctrl+C to stop
echo.

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload