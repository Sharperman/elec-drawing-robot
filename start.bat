@echo off
chcp 65001 >nul
title ElecDrawingRobot - Backend + Frontend

echo ========================================
echo   ElecDrawingRobot Start Script
echo ========================================
echo.

set PROJECT=c:\Users\li_hk\WorkBuddy\2026-05-21-08-46-52\elec-drawing-robot
set PYTHON=C:\Python314\python.exe
set NODE=C:\Users\li_hk\.workbuddy\binaries\node\versions\22.22.2\node.exe

:: Kill existing processes (targeted: only our ports)
echo [1/4] Cleaning old processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8765" ^| findstr "LISTENING"') do taskkill /PID %%a /F 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTENING"') do taskkill /PID %%a /F 2>nul
timeout /t 2 /nobreak >nul

:: Start Backend
echo [2/4] Starting Backend (port 8765)...
start "Backend-8765" /B cmd /c "cd /d %PROJECT%\backend && %PYTHON% main.py"
timeout /t 3 /nobreak >nul

:: Start Frontend
echo [3/4] Starting Frontend (port 5173)...
cd /d %PROJECT%\frontend
start "Frontend-5173" /B cmd /c "%NODE% node_modules\vite\bin\vite.js --host 0.0.0.0 --port 5173"
timeout /t 3 /nobreak >nul

:: Verify
echo [4/4] Verifying...
netstat -ano | findstr ":8765" | findstr "LISTENING" >nul && echo   [OK] Backend :8765 || echo   [FAIL] Backend :8765
netstat -ano | findstr ":5173" | findstr "LISTENING" >nul && echo   [OK] Frontend :5173 || echo   [FAIL] Frontend :5173

echo.
echo ========================================
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8765
echo ========================================
echo.
echo Press any key to stop all services...
pause >nul

:: Cleanup (targeted: only our ports)
echo Stopping services...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8765" ^| findstr "LISTENING"') do taskkill /PID %%a /F 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTENING"') do taskkill /PID %%a /F 2>nul
echo Done.
