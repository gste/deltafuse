# DeltaFuse Project Initializer for PowerShell
param (
    [string]$TargetDir = "."
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "Initializing DeltaFuse in $TargetDir..." -ForegroundColor Cyan

$dirs = @(
    "docs/process",
    "docs/init",
    "docs/decisions",
    "docs/spec",
    "docs/todo",
    "docs/todo/inbox",
    "docs/archive/init",
    "docs/archive/inbox",
    ".cursor/skills",
    ".agents/skills",
    ".gemini/skills"
)

foreach ($d in $dirs) {
    $fullPath = Join-Path $TargetDir $d
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
}

Copy-Item (Join-Path $ScriptDir "AGENTS.md") (Join-Path $TargetDir "AGENTS.md") -Force
Copy-Item (Join-Path $ScriptDir "CLAUDE.md") (Join-Path $TargetDir "CLAUDE.md") -Force
Copy-Item (Join-Path $ScriptDir "docs/process/*") (Join-Path $TargetDir "docs/process") -Recurse -Force

Copy-Item (Join-Path $ScriptDir "skills/*") (Join-Path $TargetDir ".cursor/skills") -Recurse -Force
Copy-Item (Join-Path $ScriptDir "skills/*") (Join-Path $TargetDir ".agents/skills") -Recurse -Force
Copy-Item (Join-Path $ScriptDir "skills/*") (Join-Path $TargetDir ".gemini/skills") -Recurse -Force

# Templates
if (-not (Test-Path (Join-Path $TargetDir "docs/todo/README.md"))) {
    Copy-Item (Join-Path $ScriptDir "templates/docs/todo/README.md") (Join-Path $TargetDir "docs/todo/README.md")
}
if (-not (Test-Path (Join-Path $TargetDir "docs/decisions/README.md"))) {
    Copy-Item (Join-Path $ScriptDir "templates/docs/decisions/README.md") (Join-Path $TargetDir "docs/decisions/README.md")
}
if (-not (Test-Path (Join-Path $TargetDir "docs/decisions/0000-template.md"))) {
    Copy-Item (Join-Path $ScriptDir "templates/docs/decisions/0000-template.md") (Join-Path $TargetDir "docs/decisions/0000-template.md")
}
if (-not (Test-Path (Join-Path $TargetDir "CHANGELOG.md"))) {
    Copy-Item (Join-Path $ScriptDir "templates/CHANGELOG.md") (Join-Path $TargetDir "CHANGELOG.md")
}

Write-Host "DeltaFuse initialized successfully!" -ForegroundColor Green