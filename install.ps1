$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# Prefer the py launcher, then python3, then python. Each candidate is
# probed by actually printing sys.version_info[0], so the Windows Store
# execution alias (which opens the Store instead of running Python) is
# rejected instead of silently "working".
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

Write-Error "No usable Python 3 found. Install Python 3.8+ and make sure py, python3 or python is available."
exit 1
