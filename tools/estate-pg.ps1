# estate-pg.ps1 - the one way this app starts, stops or asks about the estate's PostgreSQL.
#
#     powershell -NoProfile -ExecutionPolicy Bypass -File tools\estate-pg.ps1 start | stop [-Force] | status
#
# Platform D-028: PostgreSQL, program and data, lives on the portable drive (the
# runtime in <estate>\runtime\postgresql\17, one cluster for every app in
# <estate>\data\postgres\17, 127.0.0.1 port 5433). The estate's own script,
# <estate>\runtime\postgresql\estate-pg.js, is the only thing that starts or stops
# it (owner ruling 2026-11-03); this wrapper finds that script and a node.exe and
# hands the action over, adding a plain message and an exit code, nothing else.
# It never runs pg_ctl, never runs "init" (the PRI Suite session creates the
# cluster) and never reads a credential file.
#
# <estate> is the folder holding .estate-live, found by walking up from this app,
# so no drive letter is written anywhere. scripts\estate_pg.py (the gate and the
# switch-over) calls this file.
#
# Exit codes: 0 done or nothing to do, 1 failed, 2 usage.

param(
    [string]$Action = 'status',
    [switch]$Force
)

$ErrorActionPreference = 'Continue'
if ($Action -notin @('start', 'stop', 'status')) {
    Write-Host '  Usage: estate-pg.ps1 start | stop [-Force] | status'
    exit 2
}

# PostgreSQL refuses to run as an administrator, and its own error reads like a
# broken install, so say it plainly before doing anything.
$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host '  PostgreSQL will not run in an administrator window. Close this window and start the app from a normal one (not "Run as administrator").'
    exit 1
}

$root = Split-Path -Parent $PSScriptRoot

function Find-Estate {
    $d = $root
    while ($d) {
        if (Test-Path -LiteralPath (Join-Path $d '.estate-live') -PathType Leaf) { return $d }
        $up = Split-Path -Parent $d
        if (-not $up -or $up -eq $d) { break }
        $d = $up
    }
    return $null
}

$estate = Find-Estate
if (-not $estate) {
    Write-Host '  No .estate-live marker above this folder: this copy is outside the estate, so the drive''s PostgreSQL cannot be found.'
    exit 1
}

$js = Join-Path $estate 'runtime\postgresql\estate-pg.js'
if (-not (Test-Path -LiteralPath $js -PathType Leaf)) {
    Write-Host "  The estate's PostgreSQL script is missing: $js"
    exit 1
}

$node = $null
foreach ($c in @((Join-Path $estate 'runtime\node\node.exe'), (Join-Path $estate 'runtime\nodejs\node.exe'))) {
    if (Test-Path -LiteralPath $c -PathType Leaf) { $node = $c; break }
}
if (-not $node) {
    $cmd = Get-Command node.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { $node = $cmd.Source }
}
if (-not $node) {
    Write-Host '  Node.js was not found (under the estate runtime or on the PATH). The drive''s PostgreSQL starts and stops only through estate-pg.js, which needs Node.js. Install Node.js from nodejs.org.'
    exit 1
}

$nodeArgs = @($js, $Action)
if ($Action -eq 'stop' -and $Force) { $nodeArgs += '--force' }
& $node @nodeArgs
exit $LASTEXITCODE
