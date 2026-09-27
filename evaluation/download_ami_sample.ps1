$ErrorActionPreference = 'Stop'
$target = Join-Path $PSScriptRoot 'raw\ami'
New-Item -ItemType Directory -Force -Path $target | Out-Null

$audio = Join-Path $target 'ES2002a.Mix-Headset.wav'
$annotations = Join-Path $target 'ami_public_manual_1.6.2.zip'
$expectedAudioBytes = 40724524
$expectedAnnotationBytes = 22887865

if ((Test-Path -LiteralPath $audio) -and (Get-Item -LiteralPath $audio).Length -gt $expectedAudioBytes) {
  Remove-Item -LiteralPath $audio
}
if (-not (Test-Path -LiteralPath $audio) -or (Get-Item -LiteralPath $audio).Length -lt $expectedAudioBytes) {
  & curl.exe --fail --location --ssl-no-revoke --silent --show-error --retry 5 --retry-all-errors --continue-at - --output $audio 'https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/ES2002a/audio/ES2002a.Mix-Headset.wav'
  if ($LASTEXITCODE -ne 0) { throw 'AMI audio download failed.' }
}
if ((Get-Item -LiteralPath $audio).Length -ne $expectedAudioBytes) { throw 'AMI audio size validation failed.' }

if ((Test-Path -LiteralPath $annotations) -and (Get-Item -LiteralPath $annotations).Length -gt $expectedAnnotationBytes) {
  Remove-Item -LiteralPath $annotations
}
if (-not (Test-Path -LiteralPath $annotations) -or (Get-Item -LiteralPath $annotations).Length -lt $expectedAnnotationBytes) {
  & curl.exe --fail --location --ssl-no-revoke --silent --show-error --retry 5 --retry-all-errors --continue-at - --output $annotations 'https://groups.inf.ed.ac.uk/ami/AMICorpusAnnotations/ami_public_manual_1.6.2.zip'
  if ($LASTEXITCODE -ne 0) { throw 'AMI annotation download failed.' }
}
if ((Get-Item -LiteralPath $annotations).Length -ne $expectedAnnotationBytes) { throw 'AMI annotation size validation failed.' }

$annotationTarget = Join-Path $target 'annotations'
$wordAnnotation = Get-ChildItem -LiteralPath $annotationTarget -Recurse -Filter '*.words.xml' -File -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $wordAnnotation) {
  Expand-Archive -LiteralPath $annotations -DestinationPath $annotationTarget -Force
}

Write-Host "AMI sample ready at $target"
