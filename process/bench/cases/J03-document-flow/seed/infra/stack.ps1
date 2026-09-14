[CmdletBinding()]
param(
  [ValidateSet('validate','up','status','preserve','down')][string]$Action = 'up',
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,31}$')][string]$RunId,
  [string]$MavenRepository,
  [int]$DeadlineSeconds = 180,
  [string]$EvidenceDirectory
)
$ErrorActionPreference = 'Stop'
$seed = Split-Path -Parent $PSScriptRoot
$compose = Join-Path $seed 'compose.yaml'
$stateRoot = Join-Path $env:LOCALAPPDATA 'j03-run-state'
$stateDir = Join-Path $stateRoot $RunId
$stateFile = Join-Path $stateDir 'state.json'
$project = "j03-$RunId"

function Write-Utf8NoBom($path, $text) {
  [IO.File]::WriteAllText($path, $text, (New-Object System.Text.UTF8Encoding($false)))
}

function Set-StackEnvironment($state) {
  $env:J03_RUN_ID=$RunId; $env:J03_COMPOSE_PROJECT=$project
  $env:J03_POSTGRES_PASSWORD=$state.postgres
  $env:J03_DOCUMENT_DB_PASSWORD=$state.document
  $env:J03_WORKFLOW_DB_PASSWORD=$state.workflow
  $env:J03_AUDIT_DB_PASSWORD=$state.audit
  $env:J03_JUDGE_DB_PASSWORD=$state.judge
}
function New-Password { ([guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')) }
function Load-State {
  if (-not (Test-Path -LiteralPath $stateFile)) { throw "run state not found: $RunId" }
  Get-Content -Raw -LiteralPath $stateFile | ConvertFrom-Json
}
function Assert-Owned {
  $ids = @(docker compose -f $compose -p $project ps -q)
  if ($LASTEXITCODE -ne 0) { throw 'compose ps failed' }
  foreach ($id in $ids) {
    $labels = (docker inspect $id --format json | ConvertFrom-Json).Config.Labels
    if ($LASTEXITCODE -ne 0 -or -not $labels -or $labels.'dev.deltafuse.run' -ne $RunId) {
      throw "ownership mismatch for container $id"
    }
  }
}

if ($Action -eq 'up') {
  if (Test-Path -LiteralPath $stateFile) { throw "run id already exists: $RunId" }
  New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
  $state=[ordered]@{run_id=$RunId;project=$project;postgres=New-Password;document=New-Password;workflow=New-Password;audit=New-Password;judge=New-Password}
  Write-Utf8NoBom $stateFile ($state | ConvertTo-Json)
  Set-StackEnvironment $state
  if (-not $MavenRepository) { throw 'up requires -MavenRepository pointing to the sealed offline cache' }
  & mvn --offline "-Dmaven.repo.local=$MavenRepository" -f (Join-Path $seed 'pom.xml') package dependency:copy-dependencies -DskipTests
  if ($LASTEXITCODE -ne 0) { throw 'DEPENDENCY_CACHE_INCOMPLETE: offline Maven build failed' }
  docker compose -f $compose -p $project config --quiet
  if ($LASTEXITCODE -ne 0) { throw 'compose config validation failed' }
  docker compose -f $compose -p $project build --pull=false
  if ($LASTEXITCODE -ne 0) { throw 'offline image build failed' }
  docker compose -f $compose -p $project up -d --wait --wait-timeout $DeadlineSeconds
  if ($LASTEXITCODE -ne 0) { throw 'stack failed bounded readiness' }
  Assert-Owned
  docker compose -f $compose -p $project ps
  exit $LASTEXITCODE
}

$state=Load-State; Set-StackEnvironment $state
if ($Action -eq 'validate') { docker compose -f $compose -p $project config --quiet; exit $LASTEXITCODE }
if ($Action -eq 'status') { Assert-Owned; docker compose -f $compose -p $project ps; exit $LASTEXITCODE }
if ($Action -eq 'preserve') {
  if (-not $EvidenceDirectory) { throw 'preserve requires -EvidenceDirectory' }
  New-Item -ItemType Directory -Force -Path $EvidenceDirectory | Out-Null
  Assert-Owned
  Write-Utf8NoBom (Join-Path $EvidenceDirectory 'compose-ps.json') (docker compose -f $compose -p $project ps --format json | Out-String)
  Write-Utf8NoBom (Join-Path $EvidenceDirectory 'compose.log') (docker compose -f $compose -p $project logs --no-color | Out-String)
  exit 0
}
if ($Action -eq 'down') {
  Assert-Owned
  docker compose -f $compose -p $project down --volumes --remove-orphans
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  Remove-Item -LiteralPath $stateDir -Recurse -Force
  exit 0
}
