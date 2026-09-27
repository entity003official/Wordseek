param([int]$FrontendPid = 0, [int]$BackendPid = 0)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$hash = [BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($project))).Replace('-', '').Substring(0,16)
try {
    $existing = [Threading.Mutex]::OpenExisting("Local\BeyondWords-$hash")
    $existing.Dispose()
    Write-Output 'Beyond Words supervisor is already running: http://127.0.0.1:5173'
    exit 0
} catch [Threading.WaitHandleCannotBeOpenedException] { }
$runtime = Join-Path $project 'outputs/local-runtime' 
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
$arguments = @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + (Join-Path $PSScriptRoot 'watch_local.ps1') + '"'),'-FrontendPid',$FrontendPid,'-BackendPid',$BackendPid)
$engine = Join-Path $PSHOME 'powershell.exe'
if (-not (Test-Path -LiteralPath $engine)) { $engine = Join-Path $PSHOME 'pwsh.exe' }
Start-Process -FilePath $engine -ArgumentList $arguments -WorkingDirectory $project -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'watcher.log') -RedirectStandardError (Join-Path $runtime 'watcher.error.log') | Out-Null
Write-Output 'Beyond Words: http://127.0.0.1:5173 (background supervisor)'
