$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$GitRoot = $RepoRoot.Replace('\', '/')
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$StatePath = Join-Path $PSScriptRoot 'state.json'

$WorkDirRelative = ('tmp/a00-04-' + [Guid]::NewGuid().ToString('N'))
$WorkDir = Join-Path $RepoRoot $WorkDirRelative
$InspectProductDir = Join-Path $WorkDir 'product'
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

$State = [ordered]@{
    task_id = 'A00-04'
    criterion_id = 'BASE-004'
    framework_revision = '60ea40438b0142797848356c660ab88286565e7d'
    working_head_at_start = '03c89109a9fc0305f38733138a60c194512397c4'
    work_dir = $WorkDirRelative.Replace('\', '/')
    created_at = (Get-Date).ToString('o')
    commands = @()
}

function Write-Json($Path, $Value) {
    [System.IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 12) + "`n", $Utf8)
}

function Portable([string]$Value) {
    if ([string]::IsNullOrEmpty($Value)) { return '' }
    $replacements = [System.Collections.Generic.List[object]]::new()
    $addRepl = {
        param($from, $to)
        if (-not [string]::IsNullOrEmpty($from)) {
            $replacements.Add([PSCustomObject]@{ From = [string]$from; To = [string]$to })
            $slash = ([string]$from).Replace('\', '/')
            if ($slash -ne $from) {
                $replacements.Add([PSCustomObject]@{ From = $slash; To = [string]$to })
            }
        }
    }
    & $addRepl $InspectProductDir '<isolated-product>'
    & $addRepl $WorkDir '<run-root>'
    & $addRepl $RepoRoot '<repo>'
    if ($env:TEMP) { & $addRepl $env:TEMP '<temp-dir>' }
    $tempPath = [System.IO.Path]::GetTempPath().TrimEnd('\', '/')
    & $addRepl $tempPath '<temp-dir>'
    if ($env:USERPROFILE) { & $addRepl $env:USERPROFILE '<user-profile>' }
    if ($env:LOCALAPPDATA) { & $addRepl $env:LOCALAPPDATA '<local-appdata>' }

    $sorted = $replacements | Sort-Object { $_.From.Length } -Descending
    foreach ($r in $sorted) {
        $Value = $Value.Replace($r.From, $r.To)
    }
    $Value = [regex]::Replace($Value, 'df-smoke-[0-9a-fA-F]+', 'df-smoke-<uuid>')
    return $Value
}

function Invoke-Logged([string]$Name, [string]$Executable, [string[]]$Arguments) {
    $Attempt = 1
    while (Test-Path -LiteralPath (Join-Path $PSScriptRoot "$Name-$Attempt.txt")) { $Attempt++ }
    $RawPath = Join-Path $WorkDir "$Name-$Attempt.raw.txt"
    $OutputName = "$Name-$Attempt.txt"
    $Start = Get-Date

    & $Executable @Arguments > $RawPath 2>&1
    $ExitCode = $LASTEXITCODE
    if ($null -eq $ExitCode) { $ExitCode = 0 }
    $End = Get-Date

    $Text = [System.IO.File]::ReadAllText($RawPath)
    $PortableText = ((Portable $Text) -split '\r?\n' | ForEach-Object { $_.TrimEnd() }) -join "`n"
    if ($PortableText.Length -gt 0) { $PortableText = $PortableText.TrimEnd([char[]]"`r`n") + "`n" }
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot $OutputName), $PortableText, $Utf8)

    $Entry = [ordered]@{
        name = $Name
        attempt = $Attempt
        command = (Portable ($Executable + ' ' + ($Arguments -join ' ')))
        started_at = $Start.ToString('o')
        finished_at = $End.ToString('o')
        duration_seconds = [Math]::Round(($End - $Start).TotalSeconds, 3)
        exit_code = $ExitCode
        output = $OutputName
        raw_output = ($State.work_dir + "/$Name-$Attempt.raw.txt")
        raw_sha256 = (Get-FileHash -LiteralPath $RawPath -Algorithm SHA256).Hash.ToLowerInvariant()
        output_sha256 = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $OutputName) -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $State.commands += $Entry
    Write-Json $StatePath $State
    Write-Host "$Name attempt $Attempt : exit $ExitCode; $($Entry.duration_seconds)s; $OutputName"
    return $Entry
}

try {
    # 1. Capture Git snapshot
    $gitStatus = git -c "safe.directory=$GitRoot" status --porcelain
    $gitHead = (git -c "safe.directory=$GitRoot" rev-parse HEAD).Trim()
    $gitSnapshot = [ordered]@{
        task_id = 'A00-04'
        criterion_id = 'BASE-004'
        framework_revision = $State.framework_revision
        working_head = $gitHead
        staged_unstaged = $gitStatus
        clean = ([string]::IsNullOrWhiteSpace($gitStatus))
    }
    Write-Json (Join-Path $PSScriptRoot 'git-snapshot.json') $gitSnapshot

    # 2. Capture PowerShell & OS environment info
    $psInfo = [ordered]@{
        PSVersion = $PSVersionTable.PSVersion.ToString()
        PSEdition = $PSVersionTable.PSEdition
        PSCompatibleVersions = ($PSVersionTable.PSCompatibleVersions | ForEach-Object { $_.ToString() })
        BuildVersion = if ($PSVersionTable.BuildVersion) { $PSVersionTable.BuildVersion.ToString() } else { $null }
        OS = if ($PSVersionTable.OS) { $PSVersionTable.OS } else { [System.Environment]::OSVersion.ToString() }
        Platform = if ($PSVersionTable.Platform) { $PSVersionTable.Platform } else { [System.Environment]::OSVersion.Platform.ToString() }
        CLRVersion = if ($PSVersionTable.CLRVersion) { $PSVersionTable.CLRVersion.ToString() } else { $null }
        ProcessBitness = [System.IntPtr]::Size * 8
        HostName = $Host.Name
        HostVersion = $Host.Version.ToString()
    }
    $psInfoJson = $psInfo | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot 'powershell-info-1.txt'), $psInfoJson + "`n", $Utf8)

    # 3. Run complete tests/smoke-test.ps1
    $smokeScript = Join-Path $RepoRoot 'tests\smoke-test.ps1'
    $stepSmoke = Invoke-Logged 'smoke' 'pwsh' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $smokeScript)

    # 4. Granular step 1: Fresh init into isolated test directory
    $initScript = Join-Path $RepoRoot 'scripts\init.ps1'
    $stepInitFresh = Invoke-Logged 'init-fresh' 'pwsh' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $initScript, '-TargetDir', $InspectProductDir)

    # 5. Granular step 2: Validate layout after fresh init
    $validateScript = Join-Path $RepoRoot 'tests\validate-layout.ps1'
    $stepValidateFresh = Invoke-Logged 'validate-fresh' 'pwsh' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $validateScript, '-ProductDir', $InspectProductDir)

    # 6. Capture layout inventory of the freshly installed product
    $inventoryFiles = [System.Collections.Generic.List[object]]::new()
    Get-ChildItem -LiteralPath $InspectProductDir -Recurse -File | ForEach-Object {
        $rel = $_.FullName.Substring($InspectProductDir.Length).TrimStart('\', '/').Replace('\', '/')
        $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $inventoryFiles.Add([ordered]@{
            path = $rel
            size_bytes = $_.Length
            sha256 = $hash
        })
    }
    $lockContent = Get-Content -LiteralPath (Join-Path $InspectProductDir '.deltafuse/lock.yaml') -Raw
    $configContent = Get-Content -LiteralPath (Join-Path $InspectProductDir '.deltafuse/config.yaml') -Raw
    $inventory = [ordered]@{
        product_dir = '<isolated-product>'
        file_count = $inventoryFiles.Count
        files = $inventoryFiles
        lock = $lockContent
        config = $configContent
    }
    Write-Json (Join-Path $PSScriptRoot 'layout-inventory.json') $inventory

    # 7. Granular step 3: Idempotent reinstall with -Force
    $stepInitForce = Invoke-Logged 'init-force' 'pwsh' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $initScript, '-TargetDir', $InspectProductDir, '-Force')

    # 8. Granular step 4: Validate layout after force upgrade
    $stepValidateForce = Invoke-Logged 'validate-force' 'pwsh' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $validateScript, '-ProductDir', $InspectProductDir)

    # 9. Source integrity verification
    $gitStatusAfter = git -c "safe.directory=$GitRoot" status --porcelain
    $untrackedOutside = @()
    $changedTracked = @()
    foreach ($line in ($gitStatusAfter -split '\r?\n')) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $entry = $line.Substring(3).Trim()
        if ($entry.StartsWith('backlog/analysis/experiments/A00-04') -or $entry.StartsWith('backlog/analysis/index.md') -or $entry.StartsWith('tmp/')) {
            continue
        }
        if ($line.StartsWith('??')) {
            $untrackedOutside += $entry
        } else {
            $changedTracked += $entry
        }
    }
    $sourceIntegrity = [ordered]@{
        task_id = 'A00-04'
        repo = '<repo>'
        working_head = $gitHead
        changed_outside_expected = $changedTracked
        untracked_outside_expected = $untrackedOutside
        intact = ($changedTracked.Count -eq 0 -and $untrackedOutside.Count -eq 0)
    }
    Write-Json (Join-Path $PSScriptRoot 'source-integrity.json') $sourceIntegrity

    Write-Host "`nA00-04 PowerShell smoke and layout run complete. Intact: $($sourceIntegrity.intact)" -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $WorkDir) {
        Remove-Item -LiteralPath $WorkDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
