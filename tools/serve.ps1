# serve.ps1 - the one owner of this app's local servers.
#
#     powershell -NoProfile -ExecutionPolicy Bypass -File tools\serve.ps1 start [-Open] [-Console]
#     powershell -NoProfile -ExecutionPolicy Bypass -File tools\serve.ps1 stop
#     powershell -NoProfile -ExecutionPolicy Bypass -File tools\serve.ps1 status
#     (add -Server console, or use tools\data-console.ps1, for the Data Console)
#
# Two servers, one set of rules (owner ruling 2026-11-03, D-058):
#   site     THE MAIN PAGE. The PHP web site users see: the PHP built-in server
#            with the app folder as document root, as in the container
#            (Dockerfile), so / is index.html, /health.php the health check and
#            /php/data.php, /php/admin_ingest.php the PHP routes. tools\router.php
#            refuses the folders the container refuses. Ports 8780 to 8789.
#            PRI District Tracker.exe runs "start -Open" for this one. Start brings
#            the drive's PostgreSQL up first and stop takes it down, both through
#            tools\estate-pg.ps1 (estate-pg.js decides whether another app still
#            needs it).
#   console  THE BACKEND. The Data Console, scripts\admin_server.py, the local
#            editor of record and the Studio (never the public site). Ports 8770
#            to 8779. tools\data-console.ps1 start|stop|status runs this target.
# The rules come from the drez-local-php-runner skill:
#   - one copy of this script per folder and server at a time (a named mutex);
#   - servers bind 127.0.0.1 only, and the browser opens 127.0.0.1, never
#     localhost (that name can reach ::1 and a different server);
#   - a port is free only when no TCP listener holds it; a held port is never
#     taken over or killed: start steps to the next one in the range;
#   - a server on a port is ours only when its health check answers with this
#     app and a root that is this folder by FILE IDENTITY (volume serial plus file
#     index), never by comparing spellings, because the fixed <SystemDrive>\Estate
#     alias and the drive-letter path are one folder (owner ruling 2026-11-03, D-056);
#   - stop ends only processes whose command line names this folder, matched by
#     the same identity;
#   - every path handed to Start-Process is quoted; everything is logged to
#     data\server.log (git-ignored), each server's own output beside it;
#   - PostgreSQL refuses an administrator window, so starting the site there stops
#     with a plain message.
# The launcher starts this script hidden and does not wait, so with -Open every
# failure is also shown in a message box. -Console runs the server in this window
# for debugging (Ctrl+C stops it).
#
# Exit codes: 0 done or nothing to do, 1 failed, 2 usage.

param(
    [string]$Action = 'status',
    [switch]$Open,
    [switch]$Console,
    [string]$Server = 'site'
)

$ErrorActionPreference = 'Continue'
$AppName = 'PRI District Tracker'
$AppId   = 'pri-district-tracker'
$root    = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $root 'data'
$log     = Join-Path $dataDir 'server.log'
$wrapper = Join-Path $PSScriptRoot 'estate-pg.ps1'

if ($Action -notin @('start', 'stop', 'status') -or $Server -notin @('site', 'console')) {
    Write-Host '  Usage: serve.ps1 start [-Open] [-Console] | stop | status  [-Server site|console]'
    exit 2
}

if ($Server -eq 'site') {
    $Label  = 'The PRI District Tracker web site'
    $Ports  = 8780..8789
    $Health = '/health.php'
    $outLog = Join-Path $dataDir 'php.log'
    $errLog = Join-Path $dataDir 'php-stderr.log'
} else {
    $Label  = 'The Data Console'
    $Ports  = 8770..8779
    $Health = '/health'
    $outLog = Join-Path $dataDir 'console.log'
    $errLog = Join-Path $dataDir 'console-stderr.log'
}

function Log([string]$m) {
    try { Add-Content -LiteralPath $log -Value ('{0:yyyy-MM-dd HH:mm:ss} {1} {2} {3}' -f (Get-Date), $Server, $Action, $m) -Encoding UTF8 } catch { }
}

function Say([string]$m) { Write-Host "  $m"; Log $m }

function Fail([string]$m) {
    Write-Host "  $m"
    Log "FAILED: $m"
    if ($Open) {
        Add-Type -AssemblyName System.Windows.Forms
        [void][System.Windows.Forms.MessageBox]::Show($m, $AppName, 'OK', 'Warning')
    }
    exit 1
}

# --- Folder identity -----------------------------------------------------------
# Volume serial number plus file index: the same for every spelling of one folder
# (a mount such as the fixed Estate folder, a subst letter, a junction), different
# for a copy.
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class DtFolderId {
    [StructLayout(LayoutKind.Sequential)]
    struct BY_HANDLE_FILE_INFORMATION {
        public uint Attributes; public long Created, Accessed, Written;
        public uint VolumeSerial, SizeHigh, SizeLow, Links, IndexHigh, IndexLow;
    }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateFileW(string name, uint access, uint share, IntPtr sec, uint disposition, uint flags, IntPtr template);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool GetFileInformationByHandle(IntPtr h, out BY_HANDLE_FILE_INFORMATION info);
    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr h);
    // FILE_FLAG_BACKUP_SEMANTICS opens a directory; share read, write and delete.
    public static string Of(string path) {
        IntPtr h = CreateFileW(path, 0, 7, IntPtr.Zero, 3, 0x02000000, IntPtr.Zero);
        if (h == new IntPtr(-1)) return null;
        try {
            BY_HANDLE_FILE_INFORMATION i;
            if (!GetFileInformationByHandle(h, out i)) return null;
            return i.VolumeSerial.ToString("x8") + ":" + i.IndexHigh.ToString("x8") + i.IndexLow.ToString("x8");
        } finally { CloseHandle(h); }
    }
}
'@

$rootId = [DtFolderId]::Of($root)
if (-not $rootId) { Fail "The app folder cannot be read: $root" }

function Test-SameFolder([string]$p) {
    if (-not $p -or -not (Test-Path -LiteralPath $p)) { return $false }
    return ([DtFolderId]::Of($p) -eq $rootId)
}

# --- What runs where -----------------------------------------------------------
function Get-Health([int]$port) {
    try {
        $req = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:$port$Health")
        $req.Proxy = $null
        $req.Timeout = 2000
        $resp = $req.GetResponse()
        try {
            $text = (New-Object System.IO.StreamReader($resp.GetResponseStream())).ReadToEnd()
        } finally { $resp.Close() }
        return ($text | ConvertFrom-Json)
    } catch { return $null }
}

function Get-Busy {
    @(Get-NetTCPConnection -State Listen -LocalPort $Ports -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty LocalPort -Unique)
}

function Test-Mine([int]$port) {
    $h = Get-Health $port
    return ($h -and $h.app -eq $AppId -and (Test-SameFolder ([string]$h.root)))
}

# The port this folder's server answers on, or 0.
function Find-Mine([int[]]$busy) {
    foreach ($p in $busy) { if (Test-Mine $p) { return $p } }
    return 0
}

# Processes whose command line runs THIS folder's server: php.exe with -S on
# 127.0.0.1 and this folder as -t, or py.exe or python.exe running this folder's
# scripts\admin_server.py. Any other process is left alone.
function Get-MyProcesses {
    $mine = @()
    if ($Server -eq 'site') {
        $procs = Get-CimInstance Win32_Process -Filter "Name='php.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -and $_.CommandLine -match '-S\s+127\.0\.0\.1:' }
        foreach ($p in $procs) {
            $m = [regex]::Match($p.CommandLine, '-t\s+"([^"]+)"')
            if ($m.Success -and (Test-SameFolder $m.Groups[1].Value)) { $mine += $p }
        }
    } else {
        $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -in @('py.exe', 'pyw.exe', 'python.exe', 'pythonw.exe') -and
                           $_.CommandLine -and $_.CommandLine -match 'admin_server\.py' }
        foreach ($p in $procs) {
            $m = [regex]::Match($p.CommandLine, '"?([^"]*?)\\scripts\\admin_server\.py"?')
            if ($m.Success -and (Test-SameFolder $m.Groups[1].Value)) { $mine += $p }
        }
    }
    return $mine
}

function Open-Browser([int]$port) {
    if ($Open) { Start-Process "http://127.0.0.1:$port/" }
}

# The drive's PostgreSQL, through the one wrapper. Started through ShellExecute
# (Start-Process with a window style), so postgres.exe inherits no handle of this
# script and no caller waits on a pipe it holds; the wrapper's own words are not
# captured, so a failure points at the command that shows them. Waits for the
# wrapper alone: Start-Process -Wait waits for every descendant, and postgres.exe
# is one, so it never returned (measured 2026-11-03).
function Invoke-EstatePg([string]$what) {
    $p = Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -PassThru -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $wrapper + '"'), $what)
    $null = $p.Handle   # keeps ExitCode readable after the exit (Windows PowerShell)
    if (-not $p.WaitForExit(180000)) {
        Log "estate-pg.ps1 $what did not finish in 180 s"
        return 1
    }
    Log "estate-pg.ps1 $what exited $($p.ExitCode)"
    return $p.ExitCode
}

# The PHP that runs the site: $PRI_PHP, this folder's tools\php (SETUP.bat copies
# it), then the PATH, as scripts\find_php.py searches. A portable PHP runs with -n
# and its PDO drivers loaded from its own ext folder, so no php.ini on the computer
# changes what runs.
function Get-PhpCommand {
    $tried = @()
    $cands = @()
    if ($env:PRI_PHP) { $cands += $env:PRI_PHP; $tried += "PRI_PHP ($env:PRI_PHP)" }
    $own = Join-Path $root 'tools\php\php.exe'
    $cands += $own; $tried += $own
    foreach ($c in $cands) { if (Test-Path -LiteralPath $c -PathType Leaf) { $php = $c; break } }
    if (-not $php) {
        $cmd = Get-Command php.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        $tried += 'php.exe on the PATH'
        if ($cmd) { $php = $cmd.Source }
    }
    if (-not $php) { return @{ php = $null; tried = $tried } }
    $phpArgs = @()
    $ext = Join-Path (Split-Path -Parent $php) 'ext'
    if (Test-Path -LiteralPath $ext -PathType Container) {
        $phpArgs += @('-n', '-d', ('"extension_dir=' + $ext + '"'))
        foreach ($n in @('pdo_pgsql', 'pdo_sqlite', 'mbstring')) {
            if (Test-Path -LiteralPath (Join-Path $ext "php_$n.dll")) { $phpArgs += @('-d', "extension=$n") }
        }
    }
    return @{ php = $php; args = $phpArgs; tried = $tried }
}

# --- status --------------------------------------------------------------------
if ($Action -eq 'status') {
    $port = Find-Mine (Get-Busy)
    $procs = @(Get-MyProcesses)
    $ids = ($procs | ForEach-Object { $_.ProcessId }) -join ','
    if ($port) {
        Write-Host ("  {0}: running  http://127.0.0.1:{1}/  pid {2}  log {3}" -f $Server, $port, $ids, $log)
    } elseif ($procs.Count) {
        Write-Host ("  {0}: starting or not answering  pid {1}  log {2}" -f $Server, $ids, $log)
    } else {
        Write-Host ("  {0}: stopped  log {1}" -f $Server, $log)
    }
    exit 0
}

# --- start and stop: one copy of this script per folder and server -------------
$mutex = New-Object System.Threading.Mutex($false, "Local\$AppId-serve-$Server-$($rootId.Replace(':', '-'))")
$held = $false
try { $held = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $held = $true }
if (-not $held) {
    Write-Host "  Another serve.ps1 for this folder is already starting or stopping the $Server server. Try again in a few seconds."
    exit 0
}

try {
    if ($Action -eq 'stop') {
        $procs = @(Get-MyProcesses)
        foreach ($p in $procs) {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
            Log "stopped pid $($p.ProcessId): $($p.CommandLine)"
        }
        if ($procs.Count) { Say ("{0} stopped ({1} process(es))." -f $Label, $procs.Count) }
        else { Say "$Label is not running from this folder." }
        if ($Server -eq 'site') {
            # estate-pg.js stops the cluster only when no other application is connected.
            if ((Invoke-EstatePg 'stop') -ne 0) {
                Say 'PostgreSQL on the drive was left running: tools\estate-pg.ps1 stop did not finish. Run it in a normal window to read why before unplugging the drive.'
                exit 1
            }
            Say 'PostgreSQL on the drive: stop requested through estate-pg.js (it stays up while another application is connected).'
        }
        exit 0
    }

    # start
    if ($Server -eq 'site') {
        $principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
        if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
            Fail 'PostgreSQL will not run in an administrator window. Close this window and start the app from a normal one (not "Run as administrator").'
        }
        $found = Get-PhpCommand
        if (-not $found.php) { Fail ("PHP was not found. Looked at: {0}.`r`n`r`nRun SETUP.bat in this folder first; it copies the portable PHP into tools\php." -f ($found.tried -join '; ')) }
        if (-not (Test-Path -LiteralPath (Join-Path $root 'index.html'))) {
            Fail 'The main page index.html has not been built. Run py scripts\build_site.py in this folder first.'
        }
    } else {
        $py = Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $py) { Fail 'The Python launcher py was not found. Install Python 3.13 from python.org, then start the Data Console again.' }
        if (-not (Test-Path -LiteralPath (Join-Path $root 'scripts\admin_server.py'))) { Fail "The Data Console is missing from $root\scripts." }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $root 'config.local.json'))) {
        Fail 'config.local.json is missing. Run SETUP.bat in this folder first, then start the app again.'
    }

    $busy = Get-Busy
    $mine = Find-Mine $busy
    if ($mine) {
        Say "$Label already runs from this folder: http://127.0.0.1:$mine/"
        Open-Browser $mine
        exit 0
    }
    $port = $Ports | Where-Object { $busy -notcontains $_ } | Select-Object -First 1
    if (-not $port) { Fail ("Every port from {0} to {1} is held by another program, so {2} cannot start. Close one of them and start the app again." -f $Ports[0], $Ports[-1], $Label.ToLower()) }

    if ($Server -eq 'site') {
        if ((Invoke-EstatePg 'start') -ne 0) {
            Fail ("PostgreSQL on the drive did not start. Run this in a normal window to read why:`r`n" +
                  'powershell -NoProfile -ExecutionPolicy Bypass -File tools\estate-pg.ps1 start')
        }
        $router = Join-Path $PSScriptRoot 'router.php'
        $argList = @($found.args) + @('-S', "127.0.0.1:$port", '-t', ('"' + $root + '"'), ('"' + $router + '"'))
        $exe = $found.php
    } else {
        $env:PRI_CONSOLE_PORT = "$port"
        $env:PRI_NO_BROWSER = '1'
        $env:PYTHONUNBUFFERED = '1'
        $argList = @(('"' + (Join-Path $root 'scripts\admin_server.py') + '"'))
        $exe = $py.Source
    }

    if ($Console) {
        Say "$Label in this window: http://127.0.0.1:$port/ (Ctrl+C stops it)."
        if ($Open) { Start-Process "http://127.0.0.1:$port/" }
        $p = Start-Process -FilePath $exe -ArgumentList $argList -WorkingDirectory $root -NoNewWindow -Wait -PassThru
        exit $p.ExitCode
    }

    Log "starting on 127.0.0.1:$port with $exe"
    Start-Process -FilePath $exe -ArgumentList $argList -WorkingDirectory $root `
        -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog | Out-Null

    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 400
        if (Test-Mine $port) {
            $stopCmd = if ($Server -eq 'site') { 'tools\serve.ps1 stop' } else { 'tools\data-console.ps1 stop' }
            Say "$Label runs from this folder: http://127.0.0.1:$port/ (stop it with $stopCmd)."
            Open-Browser $port
            exit 0
        }
    }
    $tail = ''
    if (Test-Path -LiteralPath $errLog) { $tail = ((Get-Content -LiteralPath $errLog -Tail 6) -join "`r`n") }
    Fail ("{0} did not answer on http://127.0.0.1:{1}/ within 16 seconds.`r`n`r`n{2}`r`n`r`nThe whole log: {3}" -f $Label, $port, $tail, $errLog)
}
finally {
    if ($held) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
