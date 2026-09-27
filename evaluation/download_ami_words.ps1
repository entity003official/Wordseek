$ErrorActionPreference = 'Stop'
$target = Join-Path $PSScriptRoot 'raw\ami\annotations\ami_public_manual_1.6.2\words'
New-Item -ItemType Directory -Force -Path $target | Out-Null
$base = 'https://huggingface.co/datasets/ggfox00000/dia-AMICorpus-all/resolve/main/ami_public_manual_1.6.2/words'

foreach ($speaker in @('A', 'B', 'C', 'D')) {
  $name = "ES2002a.$speaker.words.xml"
  $destination = Join-Path $target $name
  if (-not (Test-Path -LiteralPath $destination) -or (Get-Item -LiteralPath $destination).Length -lt 1000) {
    & curl.exe --fail --location --ssl-no-revoke --silent --show-error --retry 5 --retry-all-errors --output $destination "$base/$name"
    if ($LASTEXITCODE -ne 0) { throw "AMI word annotation download failed: $name" }
  }
  [xml]$document = Get-Content -LiteralPath $destination -Raw
  if (-not $document.DocumentElement) { throw "AMI word annotation is invalid: $name" }
}

Write-Host "AMI ES2002a word annotations ready at $target"
