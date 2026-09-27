$ErrorActionPreference = 'Stop'
$target = Join-Path $PSScriptRoot 'raw\ami'
New-Item -ItemType Directory -Force -Path $target | Out-Null

$url = 'https://groups.inf.ed.ac.uk/ami/AMICorpusAnnotations/ami_public_manual_1.6.2.zip'
$destination = Join-Path $target 'ami_public_manual_1.6.2.zip'
$temporary = Join-Path $target 'ami_public_manual_1.6.2.complete.tmp'
$expectedBytes = 22887865
$partCount = 6
$partSize = [math]::Ceiling($expectedBytes / $partCount)
$partPaths = @()
$jobs = @()
$complete = $false

try {
  for ($index = 0; $index -lt $partCount; $index++) {
    $start = $index * $partSize
    $end = [math]::Min($expectedBytes - 1, (($index + 1) * $partSize) - 1)
    $partPath = Join-Path $target ("ami-annotations.part{0}" -f $index)
    $partPaths += $partPath
    $jobs += Start-Job -ScriptBlock {
      param($sourceUrl, $rangeStart, $rangeEnd, $outputPath)
      $expectedLength = $rangeEnd - $rangeStart + 1
      $currentLength = if (Test-Path -LiteralPath $outputPath) { (Get-Item -LiteralPath $outputPath).Length } else { 0 }
      if ($currentLength -gt $expectedLength) {
        Remove-Item -LiteralPath $outputPath
        $currentLength = 0
      }
      $exitCode = 0
      if ($currentLength -lt $expectedLength) {
        $remainingStart = $rangeStart + $currentLength
        $tailPath = "$outputPath.tail"
        Remove-Item -LiteralPath $tailPath -Force -ErrorAction SilentlyContinue
        & curl.exe --fail --location --ssl-no-revoke --silent --show-error --retry 5 --retry-all-errors --range "$remainingStart-$rangeEnd" --output $tailPath $sourceUrl
        $exitCode = $LASTEXITCODE
        if ($exitCode -eq 0 -and (Get-Item -LiteralPath $tailPath).Length -eq ($expectedLength - $currentLength)) {
          $append = [System.IO.File]::Open($outputPath, [System.IO.FileMode]::Append)
          $tail = [System.IO.File]::OpenRead($tailPath)
          try { $tail.CopyTo($append) } finally { $tail.Dispose(); $append.Dispose() }
        } elseif ($exitCode -eq 0) {
          $exitCode = 23
        }
        Remove-Item -LiteralPath $tailPath -Force -ErrorAction SilentlyContinue
      }
      [pscustomobject]@{ ExitCode = $exitCode; Path = $outputPath; Start = $rangeStart; End = $rangeEnd }
    } -ArgumentList $url, $start, $end, $partPath
  }

  Wait-Job -Job $jobs | Out-Null
  $results = @($jobs | Receive-Job)
  if ($results.Count -ne $partCount -or ($results | Where-Object { $_.ExitCode -ne 0 })) {
    throw 'One or more AMI annotation chunks failed to download.'
  }
  foreach ($result in $results) {
    $expectedPartBytes = $result.End - $result.Start + 1
    if ((Get-Item -LiteralPath $result.Path).Length -ne $expectedPartBytes) {
      throw "AMI annotation chunk has the wrong size: $($result.Path)"
    }
  }

  $output = [System.IO.File]::Create($temporary)
  try {
    foreach ($partPath in $partPaths) {
      $input = [System.IO.File]::OpenRead($partPath)
      try { $input.CopyTo($output) } finally { $input.Dispose() }
    }
  } finally {
    $output.Dispose()
  }
  if ((Get-Item -LiteralPath $temporary).Length -ne $expectedBytes) {
    throw 'Combined AMI annotation archive has the wrong size.'
  }

  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $archive = [System.IO.Compression.ZipFile]::OpenRead($temporary)
  try {
    if ($archive.Entries.Count -lt 100) { throw 'AMI annotation archive did not pass ZIP validation.' }
  } finally {
    $archive.Dispose()
  }
  Move-Item -LiteralPath $temporary -Destination $destination -Force
  $complete = $true
  Write-Host "Validated AMI annotation archive ready at $destination"
} finally {
  if ($jobs) { $jobs | Remove-Job -Force -ErrorAction SilentlyContinue }
  if ($complete) {
    foreach ($partPath in $partPaths) { Remove-Item -LiteralPath $partPath -Force -ErrorAction SilentlyContinue }
  }
  Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
}
