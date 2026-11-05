# data-console.ps1 - start, stop or ask about the Data Console, the BACKEND.
#
#     powershell -NoProfile -ExecutionPolicy Bypass -File tools\data-console.ps1 start [-Open] [-Console]
#     powershell -NoProfile -ExecutionPolicy Bypass -File tools\data-console.ps1 stop
#     powershell -NoProfile -ExecutionPolicy Bypass -File tools\data-console.ps1 status
#
# The Data Console (scripts\admin_server.py) is the local editor of record and the
# Studio, never the public site. The main page, the PHP web site, is what
# PRI District Tracker.exe and tools\serve.ps1 start. This file only hands its
# action to tools\serve.ps1 -Server console, so both servers follow one set of
# rules: one copy per folder, 127.0.0.1 only, its own server known by file
# identity, stop ends only this folder's processes. Ports 8770 to 8779.

param(
    [string]$Action = 'status',
    [switch]$Open,
    [switch]$Console
)

& (Join-Path $PSScriptRoot 'serve.ps1') -Action $Action -Open:$Open -Console:$Console -Server console
exit $LASTEXITCODE
