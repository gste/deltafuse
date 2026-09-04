# DeltaFuse end-to-end smoke test for PowerShell
$ErrorActionPreference = "Stop"
$FrameworkRoot = Split-Path -Parent $PSScriptRoot
$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("df-smoke-" + [System.Guid]::NewGuid().ToString("n"))

try {
    Write-Host "[1/4] Running fresh installation into temporary directory..." -ForegroundColor Cyan
    & (Join-Path $FrameworkRoot "scripts\init.ps1") -TargetDir $TempDir

    Write-Host "[2/4] Validating installed product layout..." -ForegroundColor Cyan
    & (Join-Path $FrameworkRoot "tests\validate-layout.ps1") -ProductDir $TempDir

    Write-Host "[3/4] Testing idempotent upgrade with -Force..." -ForegroundColor Cyan
    & (Join-Path $FrameworkRoot "scripts\init.ps1") -TargetDir $TempDir -Force

    Write-Host "[4/4] Re-validating product layout after upgrade..." -ForegroundColor Cyan
    & (Join-Path $FrameworkRoot "tests\validate-layout.ps1") -ProductDir $TempDir

    Write-Host "Smoke test passed successfully!" -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $TempDir) {
        Remove-Item -LiteralPath $TempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
