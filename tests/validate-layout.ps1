[CmdletBinding()]
param(
    [string]$ProductDir = "."
)

$ErrorActionPreference = "Stop"
$ProductRoot = [System.IO.Path]::GetFullPath($ProductDir)
$Errors = [System.Collections.Generic.List[string]]::new()

function Require-Path {
    param([string]$RelativePath)
    if (-not (Test-Path -LiteralPath (Join-Path $ProductRoot $RelativePath))) {
        $Errors.Add("Missing required path: $RelativePath")
    }
}

function Resolve-DirLink {
    param([string]$Path)
    $item = Get-Item -LiteralPath $Path -Force
    $target = $item.Target
    if ($target -is [array]) { $target = $target[0] }
    if (-not $target) { return $item.FullName }
    if (-not [System.IO.Path]::IsPathRooted($target)) {
        $target = Join-Path (Split-Path -Parent $item.FullName) $target
    }
    return [System.IO.Path]::GetFullPath($target)
}

Require-Path ".deltafuse/config.yaml"
Require-Path ".deltafuse/lock.yaml"

$lockPath = Join-Path $ProductRoot ".deltafuse/lock.yaml"
$lockVersion = $null
$lockHash = $null
$configVersion = $null
$configPath = Join-Path $ProductRoot ".deltafuse/config.yaml"

$paths = @{
    intake = "docs/intake"
    changes = "docs/changes"
    specification = "docs/spec"
    decisions = "docs/decisions"
    archive = "docs/archive"
}
$configSource = $null
$lockSource = $null
$adapterRoots = @()

if (Test-Path -LiteralPath $configPath) {
    $configLines = Get-Content -LiteralPath $configPath
    $inPaths = $false
    $inAdapters = $false
    $inRoots = $false
    foreach ($line in $configLines) {
        if ($line -match '^\s{2}version:\s*(\S+)\s*$') {
            $configVersion = $Matches[1]
        }
        if ($line -match '^\s{2}source:\s*(\S+)\s*$') {
            $configSource = $Matches[1]
        }
        if ($line -match '^paths:\s*$') { $inPaths = $true; $inAdapters = $false; $inRoots = $false; continue }
        if ($line -match '^adapters:\s*$') { $inAdapters = $true; $inPaths = $false; continue }
        if ($inPaths) {
            if ($line -match '^\s{2}([a-zA-Z0-9_-]+):\s*(\S+)\s*$') {
                $paths[$Matches[1]] = $Matches[2].Trim()
            } elseif ($line -match '^\S') {
                $inPaths = $false
            }
        }
        if ($inAdapters -and $line -match '^\s{2}roots:\s*$') { $inRoots = $true; continue }
        if ($inRoots) {
            if ($line -match '^\s{4}-\s*(.+)\s*$') {
                $adapterRoots += $Matches[1].Trim()
            } elseif ($line -match '^\S' -or ($line -match '^\s{2}\S' -and $line -notmatch '^\s{2}roots:')) {
                $inAdapters = $false
                $inRoots = $false
            }
        }
    }
    if (-not $configVersion) {
        $Errors.Add("Config file has no requested framework version")
    }
    if (-not $configSource) {
        $Errors.Add("Config file has no requested framework source")
    }
}

if ($adapterRoots.Count -eq 0) {
    $adapterRoots = @(".agents/skills", ".cursor/skills", ".gemini/skills")
}

Require-Path $paths.intake
Require-Path $paths.changes
Require-Path $paths.specification
Require-Path $paths.decisions
Require-Path (Join-Path $paths.archive "intake")
Require-Path (Join-Path $paths.archive "changes")

foreach ($forbidden in @("docs/process", "docs/init", "docs/todo")) {
    if (Test-Path -LiteralPath (Join-Path $ProductRoot $forbidden)) {
        $Errors.Add("Legacy product path must be migrated: $forbidden")
    }
}

if (Test-Path -LiteralPath $lockPath) {
    $lock = Get-Content -LiteralPath $lockPath -Raw
    $versionMatch = [regex]::Match($lock, '(?m)^\s{2}version:\s*(\S+)\s*$')
    $sourceMatch = [regex]::Match($lock, '(?m)^\s{2}source:\s*(\S+)\s*$')
    $hashMatch = [regex]::Match($lock, '(?m)^\s{2}content_hash:\s*(sha256:[a-fA-F0-9]{64})\s*$')
    if (-not $versionMatch.Success) {
        $Errors.Add("Lock file has no framework version")
    } else {
        $lockVersion = $versionMatch.Groups[1].Value
    }
    if (-not $sourceMatch.Success) {
        $Errors.Add("Lock file has no framework source")
    } else {
        $lockSource = $sourceMatch.Groups[1].Value
    }
    if (-not $hashMatch.Success) {
        $Errors.Add("Lock file has no valid framework content hash")
    } else {
        $lockHash = $hashMatch.Groups[1].Value.ToLowerInvariant()
    }
}

if ($configVersion -and $lockVersion -and $configVersion -ne $lockVersion) {
    $Errors.Add("Requested framework version $configVersion does not match locked version $lockVersion")
}

if ($configSource -and $lockSource) {
    $normalizedConfigSource = if ($configSource -eq "deltafuse") { "deltafuse://v$configVersion" } else { $configSource }
    if ($normalizedConfigSource -ne $lockSource) {
        $Errors.Add("Requested framework source '$configSource' does not match locked source '$lockSource'")
    }
}

# 1. Validate capability catalog structure
$capabilitiesPath = Join-Path $ProductRoot (Join-Path $paths.specification "_capabilities.yaml")
if (Test-Path -LiteralPath $capabilitiesPath) {
    $capContent = Get-Content -LiteralPath $capabilitiesPath -Raw
    if ($capContent -notmatch '(?m)^schema_version:\s*2\s*$') {
        $Errors.Add("Capability catalog _capabilities.yaml missing or invalid schema_version (expected 2)")
    }
    if ($capContent -notmatch '(?m)^domains:\s*') {
        $Errors.Add("Capability catalog _capabilities.yaml missing required 'domains:' key")
    }
}

# 2. Validate changes structure
$changesRoot = Join-Path $ProductRoot $paths.changes
if (Test-Path -LiteralPath $changesRoot) {
    Get-ChildItem -LiteralPath $changesRoot -Directory | ForEach-Object {
        $changeDir = $_
        $changeName = $changeDir.Name
        if ($changeName -notmatch '^CHG-[0-9]{3,}(-[a-z0-9-]+)?$') {
            $Errors.Add("Change directory name '$changeName' does not match pattern '^CHG-[0-9]{3,}(-[a-z0-9-]+)?$'")
        }

        $requestPath = Join-Path $changeDir.FullName "request.md"
        if (-not (Test-Path -LiteralPath $requestPath)) {
            $Errors.Add("Change $changeName is missing request.md")
        }

        $changeYamlPath = Join-Path $changeDir.FullName "change.yaml"
        if (-not (Test-Path -LiteralPath $changeYamlPath)) {
            $Errors.Add("Change $changeName is missing change.yaml")
        } else {
            $cyContent = Get-Content -LiteralPath $changeYamlPath -Raw
            if ($cyContent -notmatch '(?m)^schema_version:\s*2\s*$') {
                $Errors.Add("Change $changeName change.yaml missing or invalid schema_version (expected 2)")
            }
            $idMatch = [regex]::Match($cyContent, '(?m)^id:\s*(\S+)\s*$')
            if (-not $idMatch.Success) {
                $Errors.Add("Change $changeName change.yaml missing 'id:' field")
            } elseif ($idMatch.Groups[1].Value -ne $changeName) {
                $Errors.Add("Change $changeName change.yaml id '$($idMatch.Groups[1].Value)' does not match directory name '$changeName'")
            }
            $validStatuses = @(
                'normalized', 'analyzing', 'blocked-on-decision', 'analyzed',
                'specification-proposed', 'specified', 'decomposed', 'targeting',
                'target-confirmed', 'implementing', 'implemented', 'verifying',
                'converged', 'archived', 'rejected', 'duplicate', 'not-reproduced', 'superseded'
            )
            $statusMatch = [regex]::Match($cyContent, '(?m)^status:\s*(\S+)\s*$')
            if (-not $statusMatch.Success) {
                $Errors.Add("Change $changeName change.yaml missing 'status:' field")
            } elseif ($validStatuses -notcontains $statusMatch.Groups[1].Value) {
                $Errors.Add("Change $changeName change.yaml has invalid status '$($statusMatch.Groups[1].Value)'")
            }
            if ($cyContent -notmatch '(?m)^title:\s*\S+') {
                $Errors.Add("Change $changeName change.yaml missing 'title:' field")
            }
            if ($cyContent -notmatch '(?m)^framework:\s*') {
                $Errors.Add("Change $changeName change.yaml missing 'framework:' section")
            }
        }

        $routingPath = Join-Path $changeDir.FullName "routing.yaml"
        if (Test-Path -LiteralPath $routingPath) {
            $rContent = Get-Content -LiteralPath $routingPath -Raw
            if ($rContent -notmatch '(?m)^change:\s*\S+') {
                $Errors.Add("Change $changeName routing.yaml missing 'change:' field")
            }
            if ($rContent -notmatch '(?m)^claims:\s*') {
                $Errors.Add("Change $changeName routing.yaml missing 'claims:' section")
            }
        }

        $coveragePath = Join-Path $changeDir.FullName "coverage.yaml"
        if (Test-Path -LiteralPath $coveragePath) {
            $covContent = Get-Content -LiteralPath $coveragePath -Raw
            if ($covContent -notmatch '(?m)^change:\s*\S+') {
                $Errors.Add("Change $changeName coverage.yaml missing 'change:' field")
            }
            if ($covContent -notmatch '(?m)^claims:\s*') {
                $Errors.Add("Change $changeName coverage.yaml missing 'claims:' section")
            }
        }

        $slicesDir = Join-Path $changeDir.FullName "slices"
        if (Test-Path -LiteralPath $slicesDir) {
            Get-ChildItem -LiteralPath $slicesDir -Filter "*.md" | ForEach-Object {
                $sliceContent = Get-Content -LiteralPath $_.FullName -Raw
                $fmMatch = [regex]::Match($sliceContent, '(?s)^---\r?\n(.*?)\r?\n---')
                if (-not $fmMatch.Success) {
                    $Errors.Add("Change $changeName slice $($_.Name) missing YAML frontmatter")
                } else {
                    $fm = $fmMatch.Groups[1].Value
                    if ($fm -notmatch '(?m)^id:\s*SLICE-[0-9]{2,}\s*$') {
                        $Errors.Add("Change $changeName slice $($_.Name) missing or invalid 'id:' in frontmatter")
                    }
                    if ($fm -notmatch '(?m)^primary_capability:\s*\S+') {
                        $Errors.Add("Change $changeName slice $($_.Name) missing 'primary_capability:' in frontmatter")
                    }
                    if ($fm -notmatch '(?m)^status:\s*(draft|analyzing|blocked|analyzed|specified|decomposed|verified)\s*$') {
                        $Errors.Add("Change $changeName slice $($_.Name) missing or invalid 'status:' in frontmatter")
                    }
                }
            }
        }

        $tasksDir = Join-Path $changeDir.FullName "tasks"
        if (Test-Path -LiteralPath $tasksDir) {
            Get-ChildItem -LiteralPath $tasksDir -Filter "*.md" | ForEach-Object {
                if ($_.Name -like "*template*") { return }
                $taskContent = Get-Content -LiteralPath $_.FullName -Raw
                $fmMatch = [regex]::Match($taskContent, '(?s)^---\r?\n(.*?)\r?\n---')
                if (-not $fmMatch.Success) {
                    $Errors.Add("Change $changeName task $($_.Name) missing YAML frontmatter")
                } else {
                    $fm = $fmMatch.Groups[1].Value
                    if ($fm -notmatch '(?m)^id:\s*TASK-[0-9]{3,}\s*$') {
                        $Errors.Add("Change $changeName task $($_.Name) missing or invalid 'id:' in frontmatter")
                    }
                    if ($fm -notmatch '(?m)^slice:\s*SLICE-[0-9]{2,}\s*$') {
                        $Errors.Add("Change $changeName task $($_.Name) missing or invalid 'slice:' in frontmatter")
                    }
                    if ($fm -notmatch '(?m)^status:\s*(pending|targeting|target-confirmed|implementing|implemented|verified|blocked|cancelled|superseded)\s*$') {
                        $Errors.Add("Change $changeName task $($_.Name) missing or invalid 'status:' in frontmatter")
                    }
                    if ($fm -notmatch '(?m)^kind:\s*(feature|bugfix|refactor|maintenance|documentation)\s*$') {
                        $Errors.Add("Change $changeName task $($_.Name) missing or invalid 'kind:' in frontmatter")
                    }
                }
            }
        }
    }
}

# 3. Validate decisions structure
$decisionsRoot = Join-Path $ProductRoot $paths.decisions
if (Test-Path -LiteralPath $decisionsRoot) {
    Get-ChildItem -LiteralPath $decisionsRoot -Filter "DEC-*.md" | ForEach-Object {
        if ($_.Name -eq "DEC-0000-template.md") { return }
        $decContent = Get-Content -LiteralPath $_.FullName -Raw
        $fmMatch = [regex]::Match($decContent, '(?s)^---\r?\n(.*?)\r?\n---')
        if (-not $fmMatch.Success) {
            $Errors.Add("Decision $($_.Name) missing YAML frontmatter")
        } else {
            $fm = $fmMatch.Groups[1].Value
            if ($fm -notmatch '(?m)^id:\s*DEC-[0-9]{4,}\s*$') {
                $Errors.Add("Decision $($_.Name) missing or invalid 'id:' in frontmatter")
            }
            if ($fm -notmatch '(?m)^kind:\s*(product|architecture|integration|policy|operational)\s*$') {
                $Errors.Add("Decision $($_.Name) missing or invalid 'kind:' in frontmatter")
            }
            if ($fm -notmatch '(?m)^status:\s*(proposed|accepted|rejected|superseded)\s*$') {
                $Errors.Add("Decision $($_.Name) missing or invalid 'status:' in frontmatter")
            }
            if ($fm -notmatch '(?m)^owner:\s*\S+') {
                $Errors.Add("Decision $($_.Name) missing 'owner:' in frontmatter")
            }
        }
    }
}

# 4. Validate generated skills for each configured adapter root
$skillNames = @("run", "intake", "analyze", "specify", "decompose", "declare", "implement", "verify")
foreach ($adapterRootRelative in $adapterRoots) {
    $adapterRoot = Join-Path $ProductRoot $adapterRootRelative
    if (-not (Test-Path -LiteralPath $adapterRoot)) {
        $Errors.Add("Missing configured adapter root: $adapterRootRelative")
        continue
    }

    $adapterMarker = Join-Path $adapterRoot ".deltafuse-generated.yaml"
    $linkMode = $false
    $fwRel = $null
    if (Test-Path -LiteralPath $adapterMarker) {
        $adapterMeta = Get-Content -LiteralPath $adapterMarker -Raw
        if ($adapterMeta -match '(?m)^mode:\s*link\s*$') {
            $linkMode = $true
            $srcMatch = [regex]::Match($adapterMeta, '(?m)^source:\s*(\S+)\s*$')
            if ($srcMatch.Success) { $fwRel = $srcMatch.Groups[1].Value }
            if ($lockVersion -and $adapterMeta -notmatch [regex]::Escape("generated_by: deltafuse@$lockVersion")) {
                $Errors.Add("Generated adapter version mismatch: $adapterRootRelative")
            }
            if ($lockHash -and $adapterMeta -notmatch [regex]::Escape("content_hash: $lockHash")) {
                $Errors.Add("Generated adapter hash mismatch: $adapterRootRelative")
            }
        }
    }
    if ($linkMode -and -not $fwRel -and $lockSource -and $lockSource -notmatch '^deltafuse') {
        $fwRel = $lockSource
    }

    if ($linkMode) {
        if (-not $fwRel) {
            $Errors.Add("Linked adapter $adapterRootRelative has no nested framework source")
            continue
        }
        $fwSkills = Join-Path (Join-Path $ProductRoot $fwRel) "process/skills"
        foreach ($skillName in $skillNames) {
            $skillRoot = Join-Path $adapterRoot $skillName
            $skillFile = Join-Path $skillRoot "SKILL.md"
            if (-not (Test-Path -LiteralPath $skillFile)) {
                $Errors.Add("Missing generated skill: $adapterRootRelative/$skillName/SKILL.md")
                continue
            }
            $item = Get-Item -LiteralPath $skillRoot -Force
            if (-not $item.LinkType) {
                $Errors.Add("Generated skill is not a symlink: $adapterRootRelative/$skillName")
                continue
            }
            $expected = Join-Path $fwSkills $skillName
            if (Test-Path -LiteralPath $expected) {
                $actualResolved = Resolve-DirLink $skillRoot
                $expectedResolved = [System.IO.Path]::GetFullPath($expected)
                if ($actualResolved -ne $expectedResolved) {
                    $Errors.Add("Generated skill symlink does not point at ${fwRel}/process/skills/${skillName}: $adapterRootRelative/$skillName")
                }
            } else {
                $Errors.Add("Linked adapter $adapterRootRelative source '$fwRel' is not a DeltaFuse checkout")
            }
        }
        continue
    }

    foreach ($skillName in $skillNames) {
        $skillRoot = Join-Path $adapterRoot $skillName
        $skillFile = Join-Path $skillRoot "SKILL.md"
        $marker = Join-Path $skillRoot ".deltafuse-generated.yaml"
        if (-not (Test-Path -LiteralPath $skillFile)) {
            $Errors.Add("Missing generated skill: $adapterRootRelative/$skillName/SKILL.md")
            continue
        }
        if (-not (Test-Path -LiteralPath $marker)) {
            $Errors.Add("Missing generated metadata: $adapterRootRelative/$skillName")
            continue
        }

        $skillContent = Get-Content -LiteralPath $skillFile -Raw
        if ($skillContent -notmatch '(?m)^# DO NOT EDIT: generated by DeltaFuse installer\.$') {
            $Errors.Add("Generated skill is not marked DO NOT EDIT: $adapterRootRelative/$skillName")
        }
        $metadata = Get-Content -LiteralPath $marker -Raw
        if ($lockVersion -and $metadata -notmatch [regex]::Escape("generated_by: deltafuse@$lockVersion")) {
            $Errors.Add("Generated skill version mismatch: $adapterRootRelative/$skillName")
        }
        if ($lockHash -and $metadata -notmatch [regex]::Escape("content_hash: $lockHash")) {
            $Errors.Add("Generated skill hash mismatch: $adapterRootRelative/$skillName")
        }
    }
}

if ($Errors.Count -gt 0) {
    $Errors | ForEach-Object { Write-Error $_ }
    exit 1
}

Write-Host "DeltaFuse product layout is valid." -ForegroundColor Green
