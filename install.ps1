$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# 优先 py -3，其次 python3，最后 python（逐项探针验证，避开 Windows Store 假别名）
$candidates = @(
    @{ Exe = "py"; Args = @("-3") },
    @{ Exe = "python3"; Args = @() },
    @{ Exe = "python"; Args = @() }
)

foreach ($candidate in $candidates) {
    if (-not (Get-Command $candidate.Exe -ErrorAction SilentlyContinue)) { continue }
    $probeArgs = $candidate.Args + @("-c", "import sys;print(sys.version_info[0])")
    $probe = & $candidate.Exe @probeArgs 2>$null
    if ($LASTEXITCODE -ne 0) { continue }
    if ("$probe".Trim() -ne "3") { continue }

    $runArgs = $candidate.Args + @("$ScriptDir\install.py") + $args
    & $candidate.Exe @runArgs
    exit $LASTEXITCODE
}

Write-Error "未找到可用的 Python 3，请先安装 Python 3.8+ 并确保 py / python3 / python 至少一个可用。"
exit 1
