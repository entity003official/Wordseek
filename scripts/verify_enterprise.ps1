$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $projectRoot

Write-Host "[1/7] Check secret-file isolation"
if (-not (Select-String -LiteralPath ".gitignore" -Pattern '^api-key/$' -Quiet)) {
    throw "api-key/ is missing from .gitignore"
}
if (-not (Select-String -LiteralPath ".dockerignore" -Pattern '^api-key/?$' -Quiet)) {
    throw "api-key/ is missing from .dockerignore"
}

Write-Host "[2/7] Check the Qwen-only production speech boundary"
$requiredArchiveFiles = @(
    "archive/local-speech-provider/README.zh-CN.md",
    "archive/local-speech-provider/backend/asr.py",
    "archive/local-speech-provider/backend/diarization.py",
    "archive/local-speech-provider/backend/speech_pipeline.py",
    "archive/local-speech-provider/backend/model_setup.py",
    "archive/local-speech-provider/backend/local_provider.py",
    "archive/local-speech-provider/deploy/Dockerfile.speech",
    "archive/local-speech-provider/deploy/requirements-asr.txt",
    "archive/local-speech-provider/deploy/compose.local-speech.yml",
    "archive/local-speech-provider/tests/test_diarization.py",
    "archive/local-speech-provider/evaluation/transcribe_local_sample.py"
)
foreach ($path in $requiredArchiveFiles) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing local speech archive file: $path" }
}
$activeBackendFiles = Get-ChildItem -LiteralPath "backend/app" -Recurse -File -Filter "*.py"
$forbiddenImports = $activeBackendFiles | Select-String -Pattern 'faster_whisper|pyannote|LocalSpeechProvider|archive\.local-speech-provider|archive/local-speech-provider'
if ($forbiddenImports) { throw "Active backend still references archived local speech code: $($forbiddenImports.Path -join ', ')" }
$composeText = Get-Content -LiteralPath "docker-compose.yml" -Raw
foreach ($forbidden in @("worker-gpu:", "worker-speech:", "capabilities: [gpu]", "Dockerfile.speech", "requirements-asr.txt")) {
    if ($composeText.Contains($forbidden)) { throw "Default Compose still contains legacy speech configuration: $forbidden" }
}

Write-Host "[3/7] Run frontend unit tests"
npm test -- --run

Write-Host "[4/7] Build the frontend for production"
npm run build

Write-Host "[5/7] Run backend tests"
& ".\.venv\Scripts\python.exe" -m unittest discover -s backend\tests -v

Write-Host "[6/7] Verify migrations on a fresh database"
$migrationDb = Join-Path $projectRoot "backend\data\verify_migrations.db"
$dataRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot "backend\data")) + [System.IO.Path]::DirectorySeparatorChar
$migrationDbFull = [System.IO.Path]::GetFullPath($migrationDb)
if (-not $migrationDbFull.StartsWith($dataRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe migration verification database path"
}
$oldDatabaseUrl = $env:BEYOND_WORDS_DATABASE_URL
try {
    if (Test-Path -LiteralPath $migrationDbFull) { Remove-Item -LiteralPath $migrationDbFull -Force }
    $env:BEYOND_WORDS_DATABASE_URL = "sqlite:///./backend/data/verify_migrations.db"
    & ".\.venv\Scripts\alembic.exe" upgrade head
    & ".\.venv\Scripts\alembic.exe" downgrade base
    & ".\.venv\Scripts\alembic.exe" upgrade head
} finally {
    if ($null -eq $oldDatabaseUrl) { Remove-Item Env:BEYOND_WORDS_DATABASE_URL -ErrorAction SilentlyContinue }
    else { $env:BEYOND_WORDS_DATABASE_URL = $oldDatabaseUrl }
    if (Test-Path -LiteralPath $migrationDbFull) { Remove-Item -LiteralPath $migrationDbFull -Force }
}

Write-Host "[7/7] Validate container configuration"
docker compose config --quiet
docker compose -f docker-compose.yml -f docker-compose.user-test.yml config --quiet

Write-Host "All static acceptance checks passed. API key contents were not read or printed." -ForegroundColor Green
