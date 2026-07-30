@echo off
chcp 65001 >nul
cd /d "C:\Users\li_hk\WorkBuddy\2026-05-21-08-46-52\elec-drawing-robot"

echo ========================================
echo   电气图纸绘制机器人 - Git 初始化
echo ========================================
echo.

REM 1. 初始化
echo [1/5] git init...
git init

REM 2. 暂存
echo [2/5] git add...
git add .

REM 3. 提交
echo [3/5] git commit...
git commit -m "feat: initial commit with CI/CD workflows"

REM 4. 分支
echo [4/5] 设置分支...
git branch -M main

REM 5. 推送 (尝试 SSH，失败则提示手动)
echo [5/5] 推送到 GitHub...
echo.

echo 尝试 SSH: git@github.com:Sharperman/elec-drawing-robot.git
git remote add origin git@github.com:Sharperman/elec-drawing-robot.git 2>nul
git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo PUSH SUCCESS via SSH!
    
    echo 创建 develop 分支...
    git checkout -b develop
    git push -u origin develop
    
    echo.
    echo ========================================
    echo   全部完成! 去 GitHub Actions 查看 CI
    echo ========================================
) else (
    echo.
    echo SSH 失败，尝试 HTTPS...
    git remote remove origin 2>nul
    git remote add origin https://github.com/Sharperman/elec-drawing-robot.git
    git push -u origin main
    
    if %ERRORLEVEL% EQU 0 (
        echo PUSH SUCCESS via HTTPS!
        git checkout -b develop
        git push -u origin develop
    ) else (
        echo.
        echo ========================================
        echo   git push 失败 - 请手动解决
        echo ========================================
        echo.
        echo 选项 1: 用 GitHub Desktop 推送 (最简单)
        echo   下载: https://desktop.github.com/
        echo   File -> Add local repository -> 选择本目录
        echo   Publish repository
        echo.
        echo 选项 2: 配 SSH key
        echo   ssh-keygen -t ed25519 -C "your_email"
        echo   cat ~/.ssh/id_ed25519.pub
        echo   复制到 GitHub Settings -> SSH keys
        echo.
        echo 选项 3: 挂代理
        echo   git config --global http.proxy http://127.0.0.1:7890
        echo   git push -u origin main
    )
)

pause
