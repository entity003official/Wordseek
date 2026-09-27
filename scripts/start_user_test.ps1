$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $projectRoot

$composeArgs = @(
  "compose",
  "-f", "docker-compose.yml",
  "-f", "docker-compose.user-test.yml"
)

& docker @composeArgs up -d --build
if ($LASTEXITCODE -ne 0) { throw "Failed to start the user-test stack" }

$deadline = (Get-Date).AddMinutes(3)
$ready = $false
while ((Get-Date) -lt $deadline) {
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:18080/api/v1/health/ready" -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
      $ready = $true
      break
    }
  } catch {
    Start-Sleep -Seconds 2
  }
}

if (-not $ready) { throw "The user-test gateway did not become ready within 3 minutes" }
Write-Host "User-test environment is ready: http://127.0.0.1:18080" -ForegroundColor Green
