param([int]$FrontendPid = 0, [int]$BackendPid = 0)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $project 'outputs/local-runtime'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
$hash = [BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($project))).Replace('-', '').Substring(0,16)
$mutex = New-Object Threading.Mutex($false, "Local\BeyondWords-$hash")
if (-not $mutex.WaitOne(0)) { exit 0 }
$stopFile = Join-Path $runtime 'stop.request'
$logFile = Join-Path $runtime 'supervisor.log'
function Log([string]$message) { Add-Content -LiteralPath $logFile -Value "$(Get-Date -Format o) $message" -Encoding UTF8 }
function Healthy([string]$url) {
    try { return (Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 4).StatusCode -eq 200 } catch { return $false }
}
$node = Join-Path $project '.runtime/node/node.exe'
if (-not (Test-Path -LiteralPath $node)) { $node = (Get-Command node -ErrorAction SilentlyContinue).Source }
if (-not $node) { $node = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' }
$python = Join-Path $project '.venv/Scripts/python.exe'
$portablePython = Join-Path $project '.runtime/python/python.exe'
if (Test-Path -LiteralPath $portablePython) {
    $python = $portablePython
    $env:PYTHONPATH = Join-Path $project '.venv/Lib/site-packages'
    $env:PYTHONNOUSERSITE = '1'
}
$services = @(
    @{ Name='backend'; Port=8000; Url='http://127.0.0.1:8000/api/v1/health'; Exe=$python; Args=@('-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8000'); Adopt=$BackendPid; Match='uvicorn backend.app.main:app'; Handle=$null; Failures=0; Attempts=0; NextStart=[datetime]::MinValue },
    @{ Name='frontend'; Port=5173; Url='http://127.0.0.1:5173/'; Exe=$node; Args=@(('"' + (Join-Path $project 'node_modules/vite/bin/vite.js') + '"'),'--host','127.0.0.1','--port','5173','--strictPort'); Adopt=$FrontendPid; Match='vite[/\\]bin[/\\]vite.js'; Handle=$null; Failures=0; Attempts=0; NextStart=[datetime]::MinValue }
)
function Adopt-Listener($service) {
    $listener = Get-NetTCPConnection -LocalPort $service.Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $listener) { return $false }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
    # Only explicit PIDs or absolute workspace command lines can be adopted.
    if ($process.CommandLine -notmatch $service.Match -or ($listener.OwningProcess -ne $service.Adopt -and $process.CommandLine -notlike "*$project*")) {
        Log "$($service.Name): port occupied by an unmanaged process; left untouched."
        return $true
    }
    $service.Handle = Get-Process -Id $listener.OwningProcess
    Log "$($service.Name): adopted PID $($listener.OwningProcess)"
    return $true
}
function Stop-Owned($service) {
    if ($service.Handle -and -not $service.Handle.HasExited) {
        $managedId = $service.Handle.Id
        # Process object protects against killing a reused PID.
        $service.Handle.Kill()
        Log "$($service.Name): stopped owned PID $managedId"
    }
    $service.Handle = $null
}
try {
    foreach ($service in $services) { if (-not (Test-Path -LiteralPath $service.Exe)) { throw "Missing runtime: $($service.Exe)" } }
    if (Test-Path -LiteralPath $stopFile) { Remove-Item -LiteralPath $stopFile }
    Set-Content -LiteralPath (Join-Path $runtime 'supervisor.pid') -Value $PID
    Log 'Supervisor started; health interval 10s, restart after 6 consecutive failures.'
    while (-not (Test-Path -LiteralPath $stopFile)) {
        foreach ($service in $services) {
            if ($service.Handle -and $service.Handle.HasExited) {
                Log "$($service.Name): exited, exit code $($service.Handle.ExitCode)"
                $service.Handle = $null
                $service.NextStart = (Get-Date).AddSeconds([Math]::Min(60, 5 * [Math]::Max(1,$service.Attempts)))
            }
            if (-not $service.Handle) {
                if (Adopt-Listener $service) { continue }
                if ((Get-Date) -lt $service.NextStart) { continue }
                $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
                Log "$($service.Name): starting"
                $service.Attempts++
                $launched = Start-Process -FilePath $service.Exe -ArgumentList $service.Args -WorkingDirectory $project -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime "$($service.Name)-$stamp.log") -RedirectStandardError (Join-Path $runtime "$($service.Name)-$stamp.error.log") -PassThru
                $service.Handle = $launched
                # venv launchers may spawn a child; prefer the listener process once ready.
                $deadline = (Get-Date).AddSeconds(20)
                do {
                    Start-Sleep -Milliseconds 500
                    $listener = Get-NetTCPConnection -LocalPort $service.Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
                } until ($listener -or (Get-Date) -gt $deadline -or $launched.HasExited)
                if ($listener) {
                    $candidate = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
                    if ($candidate.CommandLine -match $service.Match -and ($candidate.ProcessId -eq $launched.Id -or $candidate.ParentProcessId -eq $launched.Id)) {
                        $service.Handle = Get-Process -Id $listener.OwningProcess
                    }
                }
                $service.Failures = 0
                Log "$($service.Name): managed PID $($service.Handle.Id)"
            }
            if (Healthy $service.Url) { $service.Failures = 0; $service.Attempts = 0 }
            else {
                $service.Failures++
                Log "$($service.Name): health failure $($service.Failures)/6"
                if ($service.Failures -ge 6) { Stop-Owned $service; $service.NextStart = (Get-Date).AddSeconds(5) }
            }
        }
        Start-Sleep -Seconds 10
    }
    foreach ($service in $services) { Stop-Owned $service }
    Log 'Supervisor stopped by request.'
} catch { Log "Supervisor error: $($_.Exception.Message)"; throw }
finally { $mutex.ReleaseMutex(); $mutex.Dispose() }
