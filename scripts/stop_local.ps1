$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $project 'outputs/local-runtime'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
Set-Content -LiteralPath (Join-Path $runtime 'stop.request') -Value 'stop'
Write-Output 'Stop requested. The supervisor will stop its services within 30 seconds.'
