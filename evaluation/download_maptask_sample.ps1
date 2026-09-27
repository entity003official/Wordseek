$ErrorActionPreference = 'Stop'
$target = Join-Path $PSScriptRoot 'raw\maptask'
New-Item -ItemType Directory -Force -Path $target | Out-Null

$audio = Join-Path $target 'q1ec1.mix.wav'
$transcript = Join-Path $target 'q1ec1.txt'
$expectedAudioBytes = 21207164
$minimumTranscriptBytes = 3000

if ((Test-Path -LiteralPath $audio) -and (Get-Item -LiteralPath $audio).Length -gt $expectedAudioBytes) {
  Remove-Item -LiteralPath $audio
}
if (-not (Test-Path -LiteralPath $audio) -or (Get-Item -LiteralPath $audio).Length -lt $expectedAudioBytes) {
  & curl.exe --ssl-no-revoke --fail --location --silent --show-error --retry 5 --retry-all-errors --continue-at - --output $audio 'https://groups.inf.ed.ac.uk/maptask/signals/dialogues/q1ec1.mix.wav'
  if ($LASTEXITCODE -ne 0) { throw 'Map Task audio download failed.' }
}
if ((Get-Item -LiteralPath $audio).Length -ne $expectedAudioBytes) { throw 'Map Task audio size validation failed.' }

if (-not (Test-Path -LiteralPath $transcript) -or (Get-Item -LiteralPath $transcript).Length -lt $minimumTranscriptBytes) {
  & curl.exe --ssl-no-revoke --fail --location --silent --show-error --retry 5 --retry-all-errors --output $transcript 'https://groups.inf.ed.ac.uk/maptask/transcripts/q1ec1.txt'
  if ($LASTEXITCODE -ne 0) { throw 'Map Task transcript download failed.' }
}

Write-Host "HCRC Map Task sample ready at $target"
