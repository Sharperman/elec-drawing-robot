@echo off
chcp 65001 >nul
echo ====================================
echo 启动电气图纸绘制机器人后端服务
echo ====================================

cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    if not exist "venv\Scripts\python.exe" (
        echo [INFO] 未检测到虚拟环境，使用系统 Python...
        set PYTHON=python
    ) else (
        set PYTHON=venv\Scripts\python.exe
    )
) else (
    set PYTHON=.venv\Scripts\python.exe
)

echo [INFO] Python: %PYTHON%
echo [INFO] 启动 FastAPI 后端 (端口: 8765)...
echo.

%PYTHON% backend\main.py

if errorlevel 1 (
    echo.
    echo [ERROR] 后端启动失败，错误码: %errorlevel%
    pause
)
