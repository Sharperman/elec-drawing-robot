@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   电气图纸绘制机器人 - 一键初始化
echo ============================================
echo.

:: ===========================================
:: Step 0: 检测 Python
:: ===========================================
set PYTHON_EXE=

:: 优先级: WorkBuddy managed 3.13 > 系统 Python 3.14 > 用户 Python 3.13 > PATH
if exist "%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe" (
    set PYTHON_EXE=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe
    echo [INFO] 使用 Python (managed): %USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe
    goto :found_python
)

if exist "C:\Python314\python.exe" (
    set PYTHON_EXE=C:\Python314\python.exe
    echo [INFO] 使用 Python (系统): C:\Python314\python.exe
    goto :found_python
)

if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
    echo [INFO] 使用 Python (用户): %LOCALAPPDATA%\Programs\Python\Python313\python.exe
    goto :found_python
)

:: Fallback: 尝试 PATH 中的 python
where python >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%i in ('where python') do (
        set PYTHON_EXE=%%i
        echo [INFO] 使用 Python (PATH): %%i
        goto :found_python
    )
)

echo [ERROR] 未找到 Python！请安装 Python 3.10+ 后重试。
echo         下载地址: https://www.python.org/downloads/
pause
exit /b 1

:found_python
"%PYTHON_EXE%" --version
echo.

:: ===========================================
:: Step 1: 创建虚拟环境
:: ===========================================
echo [STEP 1/4] 创建 Python 虚拟环境...

cd /d "%~dp0"

if not exist ".venv" (
    echo [INFO] 正在创建 .venv ...
    "%PYTHON_EXE%" -m venv .venv
    if errorlevel 1 (
        echo [ERROR] 创建虚拟环境失败！
        pause
        exit /b 1
    )
    echo [OK] 虚拟环境创建成功
) else (
    echo [INFO] .venv 已存在，跳过创建
)
echo.

:: ===========================================
:: Step 2: 安装 Python 依赖
:: ===========================================
echo [STEP 2/4] 安装 Python 依赖...

call .venv\Scripts\activate.bat

echo [INFO] 升级 pip...
python -m pip install --upgrade pip --quiet

echo [INFO] 安装依赖包 (可能需要几分钟)...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Python 依赖安装失败！请检查网络连接后重试。
    pause
    exit /b 1
)
echo [OK] Python 依赖安装完成
echo.

:: ===========================================
:: Step 3: 检查 Node.js 依赖
:: ===========================================
echo [STEP 3/4] 检查 Node.js 依赖...

if exist "frontend\node_modules" (
    echo [INFO] frontend\node_modules 已存在，跳过
) else (
    echo [INFO] 正在安装 Node.js 依赖...
    cd frontend
    call npm install
    if errorlevel 1 (
        echo [WARNING] npm install 失败，请手动执行: cd frontend ^&^& npm install
    ) else (
        echo [OK] Node.js 依赖安装完成
    )
    cd ..
)
echo.

:: ===========================================
:: Step 4: 初始化数据库
:: ===========================================
echo [STEP 4/4] 初始化数据库...

:: 确保 data 目录存在
if not exist "backend\data\db" mkdir "backend\data\db"
if not exist "backend\data\chroma" mkdir "backend\data\chroma"

python scripts\init_db.py
if errorlevel 1 (
    echo [ERROR] 数据库初始化失败！
    pause
    exit /b 1
)
echo [OK] 数据库初始化完成
echo.

:: ===========================================
:: 完成
:: ===========================================
echo ============================================
echo   初始化完成！
echo.
echo   下一步:
echo   (1) 确认 .env 文件中的 API Key 已配置
echo   (2) 双击 scripts\start_backend.bat 启动后端
echo   (3) 新开终端: cd frontend ^&^& npm run dev
echo ============================================
echo.
pause
