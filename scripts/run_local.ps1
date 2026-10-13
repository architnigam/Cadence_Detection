param([ValidateSet('app','tests','acceptance')][string]$Mode='app')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$bundled=Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$python=if(Test-Path -LiteralPath $bundled){$bundled}else{'python'}
switch($Mode){
 'app' { & $python scripts/run_app.py --port 8767 }
 'tests' { $env:CADENCE_TEST_REAL_OCR='1'; & $python scripts/run_all_tests.py }
 'acceptance' { & $python scripts/run_pipeline_checks.py --runner cadence_detection.runtime:run_for_qa }
}
exit $LASTEXITCODE
