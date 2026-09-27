$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$handoffRoot = Join-Path $projectRoot "handoff"
$stageRoot = Join-Path $handoffRoot ".stage-enterprise-release"
$releaseZip = Join-Path $handoffRoot "Beyond-Words-Enterprise-Release-20260926.zip"
$hashFile = Join-Path $handoffRoot "Beyond-Words-Enterprise-Release-20260926.sha256"

function Assert-HandoffPath([string]$path) {
  $resolved = [System.IO.Path]::GetFullPath($path)
  $root = [System.IO.Path]::GetFullPath($handoffRoot) + [System.IO.Path]::DirectorySeparatorChar
  if (-not $resolved.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to modify a path outside the handoff directory: $resolved"
  }
}

function Copy-ReleaseItem([string]$relativePath) {
  $source = Join-Path $projectRoot $relativePath
  if (-not (Test-Path -LiteralPath $source)) { throw "Missing release item: $relativePath" }
  $destination = Join-Path $stageRoot $relativePath
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
  Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $handoffRoot | Out-Null
Assert-HandoffPath $stageRoot
Assert-HandoffPath $releaseZip
Assert-HandoffPath $hashFile
if (Test-Path -LiteralPath $stageRoot) { Remove-Item -LiteralPath $stageRoot -Recurse -Force }
if (Test-Path -LiteralPath $releaseZip) { Remove-Item -LiteralPath $releaseZip -Force }
if (Test-Path -LiteralPath $hashFile) { Remove-Item -LiteralPath $hashFile -Force }
New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null

try {
  $items = @(
    ".github", ".dockerignore", ".env.example", ".env.production.example", ".gitignore",
    "backend\app", "backend\tests", "backend\Dockerfile", "backend\requirements.txt",
    "deploy", "docs", "migrations", "scripts",
    "src", "evaluation\derived", "evaluation\README.zh-CN.md", "evaluation\datasets.json",
    "evaluation\baselines.json", "evaluation\evaluate.py", "evaluation\import_ami.py",
    "evaluation\import_maptask.py", "evaluation\transcribe_sample.py",
    "evaluation\download_ami_annotations_parallel.ps1", "evaluation\download_ami_sample.ps1",
    "evaluation\download_ami_words.ps1", "evaluation\download_maptask_sample.ps1",
    "alembic.ini", "docker-compose.yml", "docker-compose.user-test.yml", "Dockerfile", "index.html", "package.json",
    "package-lock.json", "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json",
    "vite.config.ts", "README.md", "README.zh-CN.md", "README.en.md"
  )
  foreach ($item in $items) { Copy-ReleaseItem $item }
  Get-ChildItem -LiteralPath $projectRoot -File |
    Where-Object { $_.Extension -in @(".md", ".txt") } |
    ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $stageRoot $_.Name) -Force }

  Get-ChildItem -LiteralPath $stageRoot -Directory -Recurse -Force |
    Where-Object { $_.Name -in @("__pycache__", ".pytest_cache", ".mypy_cache") } |
    Sort-Object FullName -Descending |
    ForEach-Object {
      if (-not $_.FullName.StartsWith($stageRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Unexpected cache path" }
      Remove-Item -LiteralPath $_.FullName -Recurse -Force
    }
  Compress-Archive -Path (Join-Path $stageRoot "*") -DestinationPath $releaseZip -CompressionLevel Optimal
  $hash = Get-FileHash -LiteralPath $releaseZip -Algorithm SHA256
  [System.IO.File]::WriteAllText($hashFile, "$($hash.Hash)  $([System.IO.Path]::GetFileName($releaseZip))`n", [System.Text.UTF8Encoding]::new($false))
  Write-Host "Created: $releaseZip"
  Write-Host "SHA256: $($hash.Hash)"
} finally {
  Assert-HandoffPath $stageRoot
  if (Test-Path -LiteralPath $stageRoot) { Remove-Item -LiteralPath $stageRoot -Recurse -Force }
}
