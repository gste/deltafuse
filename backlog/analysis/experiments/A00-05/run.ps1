$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$GitRoot = $RepoRoot.Replace('\', '/')
$WslRepoRoot = '/mnt/' + $RepoRoot.Substring(0,1).ToLower() + '/' + $RepoRoot.Substring(3).Replace('\', '/')
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$StatePath = Join-Path $PSScriptRoot 'state.json'

$RunUuid = [Guid]::NewGuid().ToString('N')
$WslWorkDir = "/tmp/a00-05-$RunUuid"
$WslSourceDir = "$WslWorkDir/source"
$WslProductDir = "$WslWorkDir/product"
$ArchiveFile = Join-Path ([System.IO.Path]::GetTempPath()) ("df-archive-" + $RunUuid + ".tar")
$WslArchiveFile = '/mnt/' + $ArchiveFile.Substring(0,1).ToLower() + '/' + $ArchiveFile.Substring(3).Replace('\', '/')

$State = [ordered]@{
    task_id = 'A00-05'
    criterion_id = 'BASE-005'
    framework_revision = '60ea40438b0142797848356c660ab88286565e7d'
    working_head_at_start = 'd9ca00f40d42171120f3e6c0cbe27ef48ae5bb9a'
    work_dir = $WslWorkDir
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
    & $addRepl $WslProductDir '<isolated-product>'
    & $addRepl $WslSourceDir '<isolated-source>'
    & $addRepl $WslWorkDir '<run-root>'
    & $addRepl $WslRepoRoot '<repo>'
    & $addRepl $RepoRoot '<repo>'
    
    # Regex sanitize temp product directories before general temp path replacement
    $Value = [regex]::Replace($Value, '/tmp/tmp\.[0-9a-zA-Z]+', '<temp-dir>/df-smoke-<uuid>')
    $Value = [regex]::Replace($Value, '/tmp/df-smoke-[0-9a-fA-F]+', '<temp-dir>/df-smoke-<uuid>')
    $Value = [regex]::Replace($Value, 'df-smoke-[0-9a-fA-F]+', 'df-smoke-<uuid>')

    & $addRepl '/tmp' '<temp-dir>'
    if ($env:TEMP) { & $addRepl $env:TEMP '<temp-dir>' }
    $tempPath = [System.IO.Path]::GetTempPath().TrimEnd('\', '/')
    & $addRepl $tempPath '<temp-dir>'
    if ($env:USERPROFILE) { & $addRepl $env:USERPROFILE '<user-profile>' }
    if ($env:LOCALAPPDATA) { & $addRepl $env:LOCALAPPDATA '<local-appdata>' }

    $sorted = $replacements | Sort-Object { $_.From.Length } -Descending
    foreach ($r in $sorted) {
        $Value = $Value.Replace($r.From, $r.To)
    }
    return $Value
}

function Invoke-Logged([string]$Name, [string]$Executable, [string[]]$Arguments) {
    $Attempt = 1
    while (Test-Path -LiteralPath (Join-Path $PSScriptRoot "$Name-$Attempt.txt")) { $Attempt++ }
    $TempOutputFile = [System.IO.Path]::GetTempFileName()
    $OutputName = "$Name-$Attempt.txt"
    $Start = Get-Date

    & $Executable @Arguments > $TempOutputFile 2>&1
    $ExitCode = $LASTEXITCODE
    if ($null -eq $ExitCode) { $ExitCode = 0 }
    $End = Get-Date

    $Text = [System.IO.File]::ReadAllText($TempOutputFile)
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
        raw_sha256 = (Get-FileHash -LiteralPath $TempOutputFile -Algorithm SHA256).Hash.ToLowerInvariant()
        output_sha256 = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $OutputName) -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    Remove-Item -LiteralPath $TempOutputFile -Force -ErrorAction SilentlyContinue
    $State.commands += $Entry
    Write-Json $StatePath $State
    Write-Host "$Name attempt $Attempt : exit $ExitCode; $($Entry.duration_seconds)s; $OutputName"
    return $Entry
}

try {
    # 1. Git snapshot
    $gitStatus = git -c "safe.directory=$GitRoot" status --porcelain
    $gitHead = (git -c "safe.directory=$GitRoot" rev-parse HEAD).Trim()
    $gitSnapshot = [ordered]@{
        task_id = 'A00-05'
        criterion_id = 'BASE-005'
        framework_revision = $State.framework_revision
        working_head = $gitHead
        staged_unstaged = $gitStatus
        clean = ([string]::IsNullOrWhiteSpace($gitStatus))
    }
    Write-Json (Join-Path $PSScriptRoot 'git-snapshot.json') $gitSnapshot

    # 2. Capture Bash & Linux OS environment info
    $stepBashInfo = Invoke-Logged 'bash-info' 'bash' @('-c', 'echo "=== UNAME ==="; uname -a; echo "=== BASH ==="; bash --version | head -n 2; echo "=== OS-RELEASE ==="; cat /etc/os-release | grep -E "^(PRETTY_NAME|VERSION_ID|ID)="; echo "=== UTILITIES ==="; which awk sed sha256sum find tr mktemp tar')

    # 3. Direct execution on Windows checkout (demonstrating CRLF defect in working tree)
    $stepSmokeCrlf = Invoke-Logged 'smoke-crlf-fail' 'bash' @('tests/smoke-test.sh')

    # 4. Export clean tar archive from revision 60ea404 with core.autocrlf=false (preserving LF)
    & git -c core.autocrlf=false archive --format=tar --output=$ArchiveFile $State.framework_revision
    $archiveHash = (Get-FileHash -LiteralPath $ArchiveFile -Algorithm SHA256).Hash.ToLowerInvariant()
    $State.source_archive_sha256 = $archiveHash
    Write-Json $StatePath $State

    # 5. Extract into isolated WSL directories
    & bash -c "mkdir -p '$WslSourceDir' '$WslProductDir' && tar -xf '$WslArchiveFile' -C '$WslSourceDir'"

    # 6. Run tests/smoke-test.sh in isolated Linux source directory
    $stepSmoke = Invoke-Logged 'smoke' 'bash' @('-c', "cd '$WslSourceDir' && bash tests/smoke-test.sh")

    # 7. Granular step 1: Fresh init
    $stepInitFresh = Invoke-Logged 'init-fresh' 'bash' @('-c', "bash '$WslSourceDir/scripts/init.sh' '$WslProductDir'")

    # 8. Granular step 2: Validate fresh layout
    $stepValidateFresh = Invoke-Logged 'validate-fresh' 'bash' @('-c', "bash '$WslSourceDir/tests/validate-layout.sh' '$WslProductDir'")

    # 9. Capture layout inventory from isolated Linux product directory
    $hashLines = (& bash -c "cd '$WslProductDir' && find . -type f -exec sha256sum {} + | LC_ALL=C sort") -split '\r?\n'
    $sizeLines = (& bash -c "cd '$WslProductDir' && find . -type f -exec stat -c '%s %n' {} + | LC_ALL=C sort -k 2") -split '\r?\n'
    $sizeMap = @{}
    foreach ($line in $sizeLines) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $parts = $line.Split(' ', 2)
        if ($parts.Count -eq 2) {
            $pathKey = [regex]::Replace($parts[1].Trim(), '^\./', '')
            $sizeMap[$pathKey] = [int64]$parts[0]
        }
    }
    $inventoryFiles = [System.Collections.Generic.List[object]]::new()
    foreach ($line in $hashLines) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $parts = -split $line
        if ($parts.Count -ge 2) {
            $h = $parts[0]
            $p = [regex]::Replace($parts[1].Trim(), '^\./', '')
            $sz = if ($sizeMap.ContainsKey($p)) { $sizeMap[$p] } else { 0 }
            $inventoryFiles.Add([ordered]@{
                path = $p
                size_bytes = $sz
                sha256 = $h
            })
        }
    }
    $lockContent = (& bash -c "cat '$WslProductDir/.deltafuse/lock.yaml'") -join "`n"
    $configContent = (& bash -c "cat '$WslProductDir/.deltafuse/config.yaml'") -join "`n"
    $inventory = [ordered]@{
        product_dir = '<isolated-product>'
        file_count = $inventoryFiles.Count
        files = $inventoryFiles
        lock = $lockContent
        config = $configContent
    }
    Write-Json (Join-Path $PSScriptRoot 'layout-inventory.json') $inventory

    # 10. Granular step 3: Idempotent force upgrade
    $stepInitForce = Invoke-Logged 'init-force' 'bash' @('-c', "bash '$WslSourceDir/scripts/init.sh' --force '$WslProductDir'")

    # 11. Granular step 4: Validate post-upgrade layout
    $stepValidateForce = Invoke-Logged 'validate-force' 'bash' @('-c', "bash '$WslSourceDir/tests/validate-layout.sh' '$WslProductDir'")

    # 12. Clean up WSL temporary directory & archive file
    & bash -c "rm -rf '$WslWorkDir'"
    Remove-Item -LiteralPath $ArchiveFile -Force -ErrorAction SilentlyContinue

    # 13. Source integrity check on Windows repo
    $gitStatusAfter = git -c "safe.directory=$GitRoot" status --porcelain
    $untrackedOutside = @()
    $changedTracked = @()
    foreach ($line in ($gitStatusAfter -split '\r?\n')) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $entry = $line.Substring(3).Trim()
        if ($entry.StartsWith('backlog/analysis/experiments/A00-05') -or $entry.StartsWith('backlog/analysis/index.md') -or $entry.StartsWith('backlog/findings') -or $entry.StartsWith('tmp/')) {
            continue
        }
        if ($line.StartsWith('??')) {
            $untrackedOutside += $entry
        } else {
            $changedTracked += $entry
        }
    }
    $sourceIntegrity = [ordered]@{
        task_id = 'A00-05'
        repo = '<repo>'
        working_head = $gitHead
        changed_outside_expected = $changedTracked
        untracked_outside_expected = $untrackedOutside
        intact = ($changedTracked.Count -eq 0 -and $untrackedOutside.Count -eq 0)
    }
    Write-Json (Join-Path $PSScriptRoot 'source-integrity.json') $sourceIntegrity

    Write-Host "`nA00-05 Bash smoke and layout run complete. Intact: $($sourceIntegrity.intact)" -ForegroundColor Green
}
finally {
    & bash -c "rm -rf '$WslWorkDir'" 2>$null
    if (Test-Path -LiteralPath $ArchiveFile) {
        Remove-Item -LiteralPath $ArchiveFile -Force -ErrorAction SilentlyContinue
    }
}
