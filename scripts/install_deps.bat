@echo off
chcp 65001 >nul
echo ====================================
echo 安装电气图纸绘制机器人依赖
echo ====================================

cd /d "%~dp0.."

:: ---- Python 依赖 ----
echo.
echo [STEP 1/3] 安装 Python 依赖...
echo.

if not exist ".venv" (
    echo [INFO] 创建 Python 虚拟环境...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] 创建虚拟环境失败，请确保已安装 Python 3.10+
        pause
        exit /b 1
    )
)

echo [INFO] 激活虚拟环境...
call .venv\Scripts\activate.bat

echo [INFO] 升级 pip...
python -m pip install --upgrade pip

echo [INFO] 安装 Python 包...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Python 依赖安装失败
    pause
    exit /b 1
)
echo [OK] Python 依赖安装完成

:: ---- Node.js 依赖 ----
echo.
echo [STEP 2/3] 安装 Node.js 依赖...
echo.

if not exist "frontend\node_modules" (
    cd frontend
    npm install
    if errorlevel 1 (
        echo [ERROR] npm install 失败，请确保已安装 Node.js 20+
        pause
        exit /b 1
    )
    cd ..
) else (
    echo [INFO] node_modules 已存在，跳过...
)
echo [OK] Node.js 依赖安装完成

:: ---- 初始化数据库 ----
echo.
echo [STEP 3/3] 初始化数据库...
echo.

python scripts\init_db.py
if errorlevel 1 (
    echo [WARNING] 数据库初始化失败，请手动运行: python scripts\init_db.py
) else (
    echo [OK] 数据库初始化完成
)

echo.
echo ====================================
echo 全部依赖安装完成！
echo.
echo 下一步：
echo   1. 复制 .env.example 为 .env 并填写 API Key
echo   2. 运行 scripts\start_backend.bat 启动后端
echo   3. 运行 cd frontend ^&^& npm run dev 启动前端
echo ====================================
pause
