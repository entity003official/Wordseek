$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $projectRoot

docker compose -f docker-compose.yml -f docker-compose.user-test.yml stop
if ($LASTEXITCODE -ne 0) { throw "Failed to stop the user-test stack" }
Write-Host "User-test services stopped. Persistent Docker volumes were kept." -ForegroundColor Green

