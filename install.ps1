# 把 mj-cli\bin 加进当前用户的 PATH，PowerShell / cmd 里就能直接敲 mj 或 MJ。
#
#   powershell -ExecutionPolicy Bypass -File install.ps1
#
# 只改「当前用户」的 PATH，不碰系统级设置，也不需要管理员权限。

$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
$bin = Join-Path $root 'bin'

if (-not (Test-Path (Join-Path $bin 'mj.cmd'))) {
    throw "找不到启动器：$bin\mj.cmd（请在 mj-cli 目录里运行本脚本）"
}

$python = Get-Command python -ErrorAction SilentlyContinue
$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $python -and -not $py) {
    Write-Warning "没找到 python / py。请先装 Python 3.8+（安装时勾选 Add python.exe to PATH）。"
    return
}

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$parts = @($userPath -split ';' | Where-Object { $_ })

$already = $parts | Where-Object { $_ -ieq $bin }
if (-not $already) {
    [Environment]::SetEnvironmentVariable('Path', (($parts + $bin) -join ';'), 'User')
    Write-Host "已把 $bin 加入用户 PATH（新开的窗口生效）"
} else {
    Write-Host "用户 PATH 里已经有 $bin"
}

# 当前会话立刻可用
$env:Path = "$bin;$env:Path"

Write-Host ""
Write-Host "现在可以敲："
Write-Host "  mj            静音（小写）"
Write-Host "  MJ            带音乐（大写，cmd 里可靠）"
Write-Host "  mj --audio    大写不生效时用这个，一定能出声"
Write-Host ""
Write-Host "提示：Windows 命令不区分大小写，若 PowerShell 把 MJ 规范化成了 mj，"
Write-Host "      就用 mj --audio，效果一样。"
Write-Host ""
Write-Host "提示：把 mj 的输出接管道（|）后中文可能乱码，先执行一次：" -ForegroundColor DarkGray
Write-Host "      [Console]::OutputEncoding = [Text.Encoding]::UTF8" -ForegroundColor DarkGray
