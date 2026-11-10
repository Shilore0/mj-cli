# 从 GitHub 拉最新代码并刷新安装（Windows 源码安装用）。
#
#   powershell -ExecutionPolicy Bypass -File .\update.ps1           # 更新
#   powershell -ExecutionPolicy Bypass -File .\update.ps1 -Check    # 只检查
#   powershell -ExecutionPolicy Bypass -File .\update.ps1 -Force    # 丢弃本地改动硬更新
#
# 装的是 deb / rpm 才不用这个；Windows 是源码安装，用这个更新。

param(
    [switch]$Check,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root

$remote = if ($env:MJ_UPDATE_REMOTE) { $env:MJ_UPDATE_REMOTE } else { 'origin' }
$branch = if ($env:MJ_UPDATE_BRANCH) { $env:MJ_UPDATE_BRANCH } else { 'main' }

function Get-Version {
    $line = Select-String -Path (Join-Path $root 'mj\__init__.py') -Pattern '__version__\s*=\s*"(.+)"' |
        Select-Object -First 1
    if ($line) { return $line.Matches[0].Groups[1].Value }
    return '未知'
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "找不到 git，先装 Git for Windows：https://git-scm.com/download/win" -ForegroundColor Red
    exit 2
}
if (-not (Test-Path (Join-Path $root '.git'))) {
    Write-Host "这个目录不是 git 仓库，没法自动更新。" -ForegroundColor Yellow
    Write-Host "如果是下载 zip 解压的：重新下载最新版覆盖（先备份改动），或改用 git clone。"
    exit 2
}

$oldVersion = Get-Version
Write-Host "当前版本：$oldVersion"
Write-Host "仓库目录：$root"

Write-Host "→ 检查 $remote/$branch …"
git fetch --tags --prune --quiet $remote
if ($LASTEXITCODE -ne 0) {
    Write-Host "拉取失败。常见原因：" -ForegroundColor Red
    Write-Host "  · 网络 / 代理：报 Failed to connect 时先打开代理"
    Write-Host "  · 代理端口变了：git config --get `"http.https://github.com.proxy`""
    Write-Host "  · 远程地址变了：git remote -v"
    exit 1
}

$behind = [int](git rev-list --count "HEAD..$remote/$branch")
$ahead = [int](git rev-list --count "$remote/$branch..HEAD")

if ($behind -eq 0) {
    Write-Host "✓ 已经是最新的（$oldVersion）" -ForegroundColor Green
    if ($ahead -gt 0) { Write-Host "  本地有 $ahead 个提交还没推到远端。" }
    exit 0
}

$newVersion = (git show "$remote/${branch}:mj/__init__.py" | Select-String '__version__\s*=\s*"(.+)"' |
    Select-Object -First 1).Matches[0].Groups[1].Value
Write-Host "  有 $behind 个新提交：$oldVersion → $newVersion"

if ($Check) {
    Write-Host ""
    Write-Host "更新：powershell -ExecutionPolicy Bypass -File .\update.ps1"
    exit 0
}

$dirty = git status --porcelain --untracked-files=no
if ($dirty -and -not $Force) {
    Write-Host ""
    Write-Host "本地有未提交的改动，先处理一下（免得覆盖你的修改）：" -ForegroundColor Yellow
    Write-Host "    git stash      # 收起来，更新完 git stash pop"
    Write-Host "    git status     # 看看改了哪些文件"
    Write-Host ""
    Write-Host "确认不要了就加 -Force："
    Write-Host "    .\update.ps1 -Force"
    exit 1
}

$oldSha = (git rev-parse HEAD).Trim()

if ($Force) {
    Write-Host "⚠️  -Force：丢弃本地对已跟踪文件的修改" -ForegroundColor Yellow
    git reset --hard "$remote/$branch" | Out-Null
} else {
    git merge --ff-only "$remote/$branch" | Out-Null
}
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "无法快进合并（本地有基于旧版本的提交）。两种选择：" -ForegroundColor Yellow
    Write-Host "    .\update.ps1 -Force             # 丢弃本地提交，对齐远端"
    Write-Host "    git rebase $remote/$branch      # 把你的提交挪到新版之上"
    exit 1
}

$assetsChanged = git diff --name-only $oldSha HEAD -- assets/
if ($assetsChanged) {
    Write-Host "  素材（assets/）也更新了，动画会跟着换成新版"
}

$installer = Join-Path $root 'install.ps1'
if (Test-Path $installer) {
    Write-Host "→ 刷新 PATH 与 PowerShell profile"
    & $installer | Out-Null
}

$newNow = Get-Version
Write-Host "✓ 更新完成：$oldVersion → $newNow" -ForegroundColor Green
Write-Host "  新开一个窗口敲 mj 就是新版本（当前窗口可直接用，函数指向的是同一个路径）"
