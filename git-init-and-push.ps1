# ============================================================
# 一键初始化 Git 仓库并推送到 GitHub
# 用法: 右键此文件 -> "使用 PowerShell 运行"
# ============================================================

$ErrorActionPreference = "Stop"
Set-Location "C:\Users\li_hk\WorkBuddy\2026-05-21-08-46-52\elec-drawing-robot"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  电气图纸绘制机器人 - Git 初始化" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查 git 可用性
Write-Host "[1/6] 检查 Git..." -ForegroundColor Yellow
try {
    git --version 2>&1 | Out-Null
    Write-Host "  Git 可用" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Git 未安装或不在 PATH 中!" -ForegroundColor Red
    Read-Host "按 Enter 退出"
    exit 1
}

# 2. 初始化
Write-Host "[2/6] git init..." -ForegroundColor Yellow
git init
Write-Host "  仓库已初始化" -ForegroundColor Green

# 3. 添加所有文件
Write-Host "[3/6] git add..." -ForegroundColor Yellow
git add .
Write-Host "  文件已暂存" -ForegroundColor Green

# 4. 提交
Write-Host "[4/6] git commit..." -ForegroundColor Yellow
git commit -m "feat: initial commit with CI/CD workflows"
Write-Host "  已提交" -ForegroundColor Green

# 5. 设置分支名
Write-Host "[5/6] 设置分支..." -ForegroundColor Yellow
git branch -M main

# 6. 添加 remote 并推送
Write-Host "[6/6] 推送到 GitHub..." -ForegroundColor Yellow

# 先尝试 SSH
$remoteUrl = "git@github.com:Sharperman/elec-drawing-robot.git"

Write-Host "  尝试 SSH: $remoteUrl" -ForegroundColor Gray
git remote add origin $remoteUrl 2>$null

try {
    git push -u origin main 2>&1 | ForEach-Object { Write-Host "  $_" }
    Write-Host ""
    Write-Host "  PUSH SUCCESS via SSH!" -ForegroundColor Green
    
    # 创建 develop 分支
    Write-Host ""
    Write-Host "[额外] 创建 develop 分支..." -ForegroundColor Yellow
    git checkout -b develop
    git push -u origin develop
    Write-Host "  develop 分支已创建并推送" -ForegroundColor Green
    
} catch {
    Write-Host "  SSH 失败，尝试 HTTPS + proxy..." -ForegroundColor Yellow
    git remote remove origin 2>$null
    
    # 检查常见代理端口
    $proxyPorts = @(7890, 10809, 7891, 1080, 8888, 8080)
    $found = $false
    
    foreach ($port in $proxyPorts) {
        $proxy = "http://127.0.0.1:$port"
        try {
            $conn = [System.Net.Sockets.TcpClient]::new()
            $task = $conn.ConnectAsync("127.0.0.1", $port)
            if ($task.Wait(500)) {
                Write-Host "  发现代理: $proxy" -ForegroundColor Green
                git config --local http.proxy $proxy
                git config --local https.proxy $proxy
                
                git remote add origin "https://github.com/Sharperman/elec-drawing-robot.git"
                git push -u origin main 2>&1 | ForEach-Object { Write-Host "  $_" }
                
                Write-Host "  PUSH SUCCESS via HTTPS proxy!" -ForegroundColor Green
                $found = $true
                
                # 创建 develop 分支
                Write-Host "  创建 develop 分支..." -ForegroundColor Yellow
                git checkout -b develop
                git push -u origin develop
                
                break
            }
            $conn.Dispose()
        } catch {}
    }
    
    if (-not $found) {
        Write-Host ""
        Write-Host "  ========================================" -ForegroundColor Red
        Write-Host "  SSH 和 HTTPS 均失败" -ForegroundColor Red
        Write-Host "  ========================================" -ForegroundColor Red
        Write-Host ""
        Write-Host "  请手动尝试以下方法之一：" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  方法A: GitHub Desktop (最简单)" -ForegroundColor White
        Write-Host "    1. 下载安装 https://desktop.github.com/" -ForegroundColor Gray
        Write-Host "    2. File -> Add local repository -> 选择本目录" -ForegroundColor Gray
        Write-Host "    3. Publish repository -> Sharperman/elec-drawing-robot" -ForegroundColor Gray
        Write-Host ""
        Write-Host "  方法B: 手动 SSH key" -ForegroundColor White
        Write-Host "    ssh-keygen -t ed25519 -C 'your_email@example.com'" -ForegroundColor Gray
        Write-Host "    cat ~/.ssh/id_ed25519.pub" -ForegroundColor Gray
        Write-Host "    复制到 GitHub -> Settings -> SSH and GPG keys" -ForegroundColor Gray
        Write-Host "    git remote add origin git@github.com:Sharperman/elec-drawing-robot.git" -ForegroundColor Gray
        Write-Host "    git push -u origin main" -ForegroundColor Gray
        Read-Host "按 Enter 退出"
        exit 1
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  全部完成! 去 GitHub Actions 查看 CI" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Read-Host "按 Enter 退出"
