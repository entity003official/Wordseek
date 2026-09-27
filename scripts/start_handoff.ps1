$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $project
foreach ($relative in @('.runtime/node/node.exe', '.runtime/python/python.exe', '.venv/Lib/site-packages/fastapi', 'node_modules/vite/bin/vite.js', 'backend/data/beyond_words_v1.db')) {
    if (-not (Test-Path -LiteralPath (Join-Path $project $relative))) { throw "Missing $relative. Extract the entire private archive first." }
}
& (Join-Path $PSScriptRoot 'start_local.ps1')
$ready = $false
$deadline = (Get-Date).AddSeconds(45)
do {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5173/api/v1/health' -TimeoutSec 3
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 1
} until ((Get-Date) -gt $deadline)
if (-not $ready) { throw 'Startup did not complete. Read outputs/local-runtime/supervisor.log and the newest *.error.log; check ports 5173 and 8000.' }
Start-Process 'http://127.0.0.1:5173/'
Write-Output 'Ready: http://127.0.0.1:5173/ . Closing this window does not stop the website.'
