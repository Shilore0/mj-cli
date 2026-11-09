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

# ---------------------------------------------------------------------------
# 在 PowerShell 里让 MJ 也带声音。
# PowerShell 解析命令时会规范化大小写，直接调用 mj.cmd 拿不到你敲的是 mj 还是 MJ。
# 所以在 profile 里放一个函数：$MyInvocation.InvocationName 保留原始大小写。
#
# Windows PowerShell 5.1 和 PowerShell 7 的 profile 不在同一个文件里，两个都要写，
# 否则在 pwsh 里 MJ 就没声音。
# ---------------------------------------------------------------------------
$exe = Join-Path $bin 'mj.cmd'
$markBegin = '# >>> mj-cli >>>'
$markEnd = '# <<< mj-cli <<<'
$block = @(
    $markBegin
    'function global:mj {'
    "    `$exe = '$exe'"
    '    $old = $env:MJ_AS'
    "    if (`$MyInvocation.InvocationName -ceq 'MJ') { `$env:MJ_AS = 'MJ' }"
    '    try { & $exe @args } finally { $env:MJ_AS = $old }'
    '}'
    $markEnd
)

$documents = [Environment]::GetFolderPath('MyDocuments')
$targets = @()
if (Get-Command powershell -ErrorAction SilentlyContinue) {
    $targets += Join-Path $documents 'WindowsPowerShell\profile.ps1'   # 5.1
}
if (Get-Command pwsh -ErrorAction SilentlyContinue) {
    $targets += Join-Path $documents 'PowerShell\profile.ps1'          # 7+
}
$targets += $PROFILE.CurrentUserAllHosts
$targets = @($targets | Where-Object { $_ } | Select-Object -Unique)

foreach ($profilePath in $targets) {
    $profileDir = Split-Path -Parent $profilePath
    if ($profileDir -and -not (Test-Path $profileDir)) {
        New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
    }

    $existing = @()
    if (Test-Path $profilePath) {
        $existing = Get-Content -Path $profilePath -Encoding UTF8
    }
    # 先去掉旧块，保证可重复执行
    $kept = @()
    $inBlock = $false
    foreach ($line in $existing) {
        if ($line -eq $markBegin) { $inBlock = $true; continue }
        if ($line -eq $markEnd) { $inBlock = $false; continue }
        if (-not $inBlock) { $kept += $line }
    }
    Set-Content -Path $profilePath -Value ($kept + $block) -Encoding UTF8
    Write-Host "已写入 mj 函数：$profilePath"
}

# 当前会话也立刻生效
Invoke-Expression ($block -join "`n")

Write-Host ""
Write-Host "现在可以敲："
Write-Host "  mj            静音（小写）"
Write-Host "  MJ            带音乐（大写）"
Write-Host "  mj --audio    显式出声"
Write-Host ""
Write-Host "（新开的 PowerShell 窗口才会加载 profile；当前窗口已临时生效）"
Write-Host ""
Write-Host "提示：把 mj 的输出接管道（|）后中文可能乱码，先执行一次：" -ForegroundColor DarkGray
Write-Host "      [Console]::OutputEncoding = [Text.Encoding]::UTF8" -ForegroundColor DarkGray
