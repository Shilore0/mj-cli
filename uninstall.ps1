# 从当前用户的 PATH 里移除 mj-cli\bin，并删掉 profile 里的 mj 函数块。
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

$markBegin = '# >>> mj-cli >>>'
$markEnd = '# <<< mj-cli <<<'
$profilePath = $PROFILE.CurrentUserAllHosts
if (-not $profilePath) { $profilePath = $PROFILE }

if (Test-Path $profilePath) {
    $lines = Get-Content -Path $profilePath -Encoding UTF8
    if ($lines -contains $markBegin) {
        $out = @()
        $inBlock = $false
        foreach ($line in $lines) {
            if ($line -eq $markBegin) { $inBlock = $true; continue }
            if ($line -eq $markEnd) { $inBlock = $false; continue }
            if (-not $inBlock) { $out += $line }
        }
        Set-Content -Path $profilePath -Value $out -Encoding UTF8
        Write-Host "已从 $profilePath 移除 mj 函数块"
    }
}

Write-Host ""
Write-Host "仓库目录 $root 没有动；不需要的话直接删除整个文件夹即可。"
