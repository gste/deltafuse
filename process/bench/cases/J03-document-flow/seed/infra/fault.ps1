[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,31}$')][string]$RunId,
  [Parameter(Mandatory=$true)][ValidateSet('postgres','kafka','document-service','workflow-service','audit-service')][string]$Service,
  [ValidateSet('stop','recover')][string]$Action = 'stop',
  [int]$DeadlineSeconds = 120
)
$ErrorActionPreference='Stop'
$seed=Split-Path -Parent $PSScriptRoot
$compose=Join-Path $seed 'compose.yaml'
$stateFile=Join-Path (Join-Path (Join-Path $env:LOCALAPPDATA 'j03-run-state') $RunId) 'state.json'
if(-not(Test-Path -LiteralPath $stateFile)){throw "run state not found: $RunId"}
$state=Get-Content -Raw -LiteralPath $stateFile|ConvertFrom-Json
$env:J03_RUN_ID=$RunId;$env:J03_COMPOSE_PROJECT=$state.project;$env:J03_POSTGRES_PASSWORD=$state.postgres;$env:J03_DOCUMENT_DB_PASSWORD=$state.document;$env:J03_WORKFLOW_DB_PASSWORD=$state.workflow;$env:J03_AUDIT_DB_PASSWORD=$state.audit;$env:J03_JUDGE_DB_PASSWORD=$state.judge
$id=docker compose -f $compose -p $state.project ps -qa $Service
if($LASTEXITCODE -ne 0 -or -not $id){throw "service is not run-owned or absent: $Service"}
$labels=(docker inspect $id --format json|ConvertFrom-Json).Config.Labels
if(-not $labels -or $labels.'dev.deltafuse.run' -ne $RunId){throw "ownership mismatch: $Service"}
if($Action -eq 'stop'){docker compose -f $compose -p $state.project stop --timeout 10 $Service;exit $LASTEXITCODE}
docker compose -f $compose -p $state.project up -d --no-deps $Service
if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}
$deadline=(Get-Date).AddSeconds($DeadlineSeconds)
do{$health=docker inspect $id --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}';if($health -eq 'healthy'){exit 0};Start-Sleep -Milliseconds 500}while((Get-Date)-lt $deadline)
throw "recovery deadline exceeded for $Service; last state=$health"
