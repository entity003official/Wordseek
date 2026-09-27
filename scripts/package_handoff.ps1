$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$handoffRoot = Join-Path $projectRoot 'handoff'
$sourceStage = Join-Path $handoffRoot '.stage-pro'
$dataStage = Join-Path $handoffRoot '.stage-evaluation'
$sourceZip = Join-Path $handoffRoot 'Beyond-Words-Source-Handoff-20260926.zip'
$dataZip = Join-Path $handoffRoot 'Beyond-Words-Evaluation-Data-20260926.zip'
$sourceHashFile = Join-Path $handoffRoot 'Beyond-Words-Source-Handoff-20260926.sha256'
$dataHashFile = Join-Path $handoffRoot 'Beyond-Words-Evaluation-Data-20260926.sha256'

function Assert-InHandoff([string]$path) {
  $full = [System.IO.Path]::GetFullPath($path)
  $root = [System.IO.Path]::GetFullPath($handoffRoot) + [System.IO.Path]::DirectorySeparatorChar
  if (-not $full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to modify a path outside the handoff directory: $full"
  }
}

function Copy-ProjectItem([string]$relativePath, [string]$stageRoot) {
  $source = Join-Path $projectRoot $relativePath
  if (-not (Test-Path -LiteralPath $source)) { throw "Required handoff item is missing: $relativePath" }
  $destination = Join-Path $stageRoot $relativePath
  $parent = Split-Path -Parent $destination
  New-Item -ItemType Directory -Force -Path $parent | Out-Null
  Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $handoffRoot | Out-Null
Assert-InHandoff $sourceStage
Assert-InHandoff $dataStage
Assert-InHandoff $sourceZip
Assert-InHandoff $dataZip
Assert-InHandoff $sourceHashFile
Assert-InHandoff $dataHashFile

foreach ($path in @($sourceStage, $dataStage)) {
  if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
  New-Item -ItemType Directory -Force -Path $path | Out-Null
}
foreach ($path in @($sourceZip, $dataZip)) {
  if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
}
foreach ($path in @($sourceHashFile, $dataHashFile)) {
  if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
}

try {
  $sourceItems = @(
    '.github',
    'src',
    'archive',
    'backend\app',
    'backend\tests',
    'backend\requirements.txt',
    'backend\Dockerfile',
    'deploy',
    'migrations',
    'evaluation\README.zh-CN.md',
    'evaluation\datasets.json',
    'evaluation\baselines.json',
    'evaluation\download_ami_annotations_parallel.ps1',
    'evaluation\download_ami_sample.ps1',
    'evaluation\download_ami_words.ps1',
    'evaluation\download_maptask_sample.ps1',
    'evaluation\evaluate.py',
    'evaluation\import_ami.py',
    'evaluation\import_maptask.py',
    'evaluation\transcribe_sample.py',
    'evaluation\derived',
    'docs',
    'scripts',
    '.dockerignore',
    '.env.example',
    '.env.production.example',
    '.gitignore',
    'alembic.ini',
    'docker-compose.yml',
    'docker-compose.user-test.yml',
    'Dockerfile',
    'index.html',
    'package.json',
    'package-lock.json',
    'tsconfig.json',
    'tsconfig.app.json',
    'tsconfig.node.json',
    'vite.config.ts'
  )
  foreach ($item in $sourceItems) { Copy-ProjectItem $item $sourceStage }
  foreach ($pattern in @('*.md', '*.txt')) {
    Get-ChildItem -Path (Join-Path $projectRoot $pattern) -File | ForEach-Object {
      Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $sourceStage $_.Name) -Force
    }
  }
  Get-ChildItem -LiteralPath $sourceStage -Directory -Recurse -Filter '__pycache__' | ForEach-Object {
    if (-not $_.FullName.StartsWith($sourceStage, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Unexpected cache path' }
    Remove-Item -LiteralPath $_.FullName -Recurse -Force
  }

  $dataItems = @(
    'evaluation\README.zh-CN.md',
    'evaluation\datasets.json',
    'evaluation\baselines.json',
    'evaluation\raw\maptask\q1ec1.mix.wav',
    'evaluation\raw\maptask\q1ec1.txt',
    'evaluation\raw\ami\ES2002a.Mix-Headset.wav',
    'evaluation\raw\ami\ami_public_manual_1.6.2.zip',
    'evaluation\derived'
  )
  foreach ($item in $dataItems) { Copy-ProjectItem $item $dataStage }

  Compress-Archive -Path (Join-Path $sourceStage '*') -DestinationPath $sourceZip -CompressionLevel Optimal
  Compress-Archive -Path (Join-Path $dataStage '*') -DestinationPath $dataZip -CompressionLevel Optimal

  $sourceHash = Get-FileHash -LiteralPath $sourceZip -Algorithm SHA256
  $dataHash = Get-FileHash -LiteralPath $dataZip -Algorithm SHA256
  [System.IO.File]::WriteAllText($sourceHashFile, "$($sourceHash.Hash)  $([System.IO.Path]::GetFileName($sourceZip))`n", [System.Text.UTF8Encoding]::new($false))
  [System.IO.File]::WriteAllText($dataHashFile, "$($dataHash.Hash)  $([System.IO.Path]::GetFileName($dataZip))`n", [System.Text.UTF8Encoding]::new($false))

  Write-Host "Created: $sourceZip"
  Write-Host "Created: $dataZip"
  Write-Host "Source SHA256: $($sourceHash.Hash)"
  Write-Host "Evaluation SHA256: $($dataHash.Hash)"
} finally {
  foreach ($path in @($sourceStage, $dataStage)) {
    Assert-InHandoff $path
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
  }
}
