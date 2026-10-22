$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

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

    $runArgs = $candidate.Args + @("$ScriptDir\uninstall.py") + $args
    & $candidate.Exe @runArgs
    exit $LASTEXITCODE
}

Write-Error "未找到可用的 Python 3，无法执行卸载。"
exit 1
