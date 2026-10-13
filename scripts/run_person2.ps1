param(
    [string[]]$Files,
    [string]$OutputDir = 'data/extracted',
    [int]$Dpi = 300,
    [string]$Regions
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies'
$bundledPython = Join-Path $runtimeRoot 'python/python.exe'
$pythonCommand = if (Test-Path -LiteralPath $bundledPython) { $bundledPython } else { 'python' }
$nodeCommand = Join-Path $runtimeRoot 'node/bin/node.exe'
$ocrModule = Join-Path $runtimeRoot 'node/node_modules/tesseract.js'
$languageDir = Join-Path $projectRoot '.local/ocr'
if ((Test-Path -LiteralPath $nodeCommand) -and (Test-Path -LiteralPath $ocrModule) -and (Test-Path -LiteralPath (Join-Path $languageDir 'eng.traineddata'))) {
    $env:CADENCE_NODE = $nodeCommand
    $env:CADENCE_TESSERACT_JS = $ocrModule
    $env:CADENCE_TESSDATA = $languageDir
}
$localTemp = Join-Path $projectRoot 'tmp/extraction'
New-Item -ItemType Directory -Force -Path $localTemp | Out-Null
$env:TMP = $localTemp
$env:TEMP = $localTemp
if (-not $Files) {
    $Files = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot 'data/source') -File |
        Where-Object { $_.Extension -in '.pdf', '.pptx', '.docx' } |
        ForEach-Object { $_.FullName })
}
if (-not $Files) { throw 'No input files found.' }
if (-not [System.IO.Path]::IsPathRooted($OutputDir)) { $OutputDir = Join-Path $projectRoot $OutputDir }
$cliArgs = @('-u', (Join-Path $PSScriptRoot 'extract_documents.py')) + $Files + @('--output-dir', $OutputDir, '--dpi', "$Dpi")
if ($Regions) { $cliArgs += @('--regions', $Regions) }
& $pythonCommand @cliArgs
exit $LASTEXITCODE
