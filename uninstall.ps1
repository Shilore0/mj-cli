# 从当前用户的 PATH 里移除 mj-cli\bin（不删仓库文件）。
#
#   powershell -ExecutionPolicy Bypass -File uninstall.ps1

$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
$bin = Join-Path $root 'bin'

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$parts = @($userPath -split ';' | Where-Object { $_ })

$kept = $parts | Where-Object { $_ -ine $bin }
if ($kept.Count -eq $parts.Count) {
    Write-Host "用户 PATH 里没有 $bin，无需改动"
} else {
    [Environment]::SetEnvironmentVariable('Path', ($kept -join ';'), 'User')
    Write-Host "已从用户 PATH 移除 $bin"
}

Write-Host ""
Write-Host "仓库目录 $root 没有动；不需要的话直接删除整个文件夹即可。"
