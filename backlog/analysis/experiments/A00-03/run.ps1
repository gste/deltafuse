param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('prepare', 'install', 'test')]
    [string]$Stage,
    [string]$PythonExecutable
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$GitRoot = $RepoRoot.Replace('\', '/')
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$StatePath = Join-Path $PSScriptRoot 'state.json'

function Write-Json($Path, $Value) {
    [System.IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 12) + "`n", $Utf8)
}

if ($Stage -eq 'prepare' -and -not (Test-Path -LiteralPath $StatePath)) {
    $State = [ordered]@{
        revision = '60ea40438b0142797848356c660ab88286565e7d'
        work_dir = ('tmp/a00-03-' + [Guid]::NewGuid().ToString('N'))
        created_at = (Get-Date).ToString('o')
        commands = @()
    }
} else {
    $State = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json -AsHashtable
}
if ($Stage -eq 'prepare' -and -not $PythonExecutable) { throw 'PythonExecutable is required for prepare.' }

$RunRoot = Join-Path $RepoRoot $State.work_dir
$Source = Join-Path $RunRoot 'source'
$Venv = Join-Path $RunRoot '.venv'
$VenvPython = Join-Path $Venv 'Scripts/python.exe'
New-Item -ItemType Directory -Force -Path $RunRoot, (Join-Path $RunRoot 'temp') | Out-Null

# Environment changes are limited to this process and its children.
foreach ($Name in @('PYTHONPATH', 'PYTHONHOME', 'PYTEST_ADDOPTS', 'PYTEST_PLUGINS', 'PYTEST_CURRENT_TEST', 'VIRTUAL_ENV')) {
    Remove-Item -LiteralPath "Env:$Name" -ErrorAction SilentlyContinue
}
$env:PYTHONNOUSERSITE = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:TEMP = Join-Path $RunRoot 'temp'
$env:TMP = $env:TEMP

function Portable([string]$Value) {
    foreach ($Pair in @(
        @($RunRoot, '<run-root>'), @($Source, '<source>'),
        @($RepoRoot, '<repo>'), @($GitRoot, '<repo>')
    )) {
        $Value = $Value.Replace($Pair[0], $Pair[1]).Replace($Pair[0].Replace('\', '/'), $Pair[1])
    }
    if ($PythonExecutable) { $Value = $Value.Replace($PythonExecutable, '<base-python>') }
    if ($env:USERPROFILE) { $Value = $Value.Replace($env:USERPROFILE, '<user-profile>') }
    return $Value
}

function Invoke-Logged([string]$Name, [string]$Executable, [string[]]$Arguments) {
    $Attempt = 1
    while (Test-Path -LiteralPath (Join-Path $PSScriptRoot "$Name-$Attempt.txt")) { $Attempt++ }
    $RawPath = Join-Path $RunRoot "$Name-$Attempt.raw.txt"
    $OutputName = "$Name-$Attempt.txt"
    $Start = Get-Date
    & $Executable @Arguments > $RawPath 2>&1
    $ExitCode = $LASTEXITCODE
    $End = Get-Date
    $Text = [System.IO.File]::ReadAllText($RawPath)
    $PortableText = ((Portable $Text) -split '\r?\n' | ForEach-Object { $_.TrimEnd() }) -join "`n"
    if ($PortableText.Length -gt 0) { $PortableText = $PortableText.TrimEnd([char[]]"`r`n") + "`n" }
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot $OutputName), $PortableText, $Utf8)
    $Entry = [ordered]@{
        name = $Name; attempt = $Attempt
        command = (Portable ($Executable + ' ' + ($Arguments -join ' ')))
        started_at = $Start.ToString('o'); finished_at = $End.ToString('o')
        duration_seconds = [Math]::Round(($End - $Start).TotalSeconds, 3)
        exit_code = $ExitCode; output = $OutputName
        raw_output = ($State.work_dir + "/$Name-$Attempt.raw.txt")
        raw_sha256 = (Get-FileHash -LiteralPath $RawPath -Algorithm SHA256).Hash.ToLowerInvariant()
        output_sha256 = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $OutputName) -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $State.commands += $Entry
    Write-Json $StatePath $State
    Write-Host "$Name attempt $Attempt : exit $ExitCode; $($Entry.duration_seconds)s; $OutputName"
    return $Entry
}

if ($Stage -eq 'prepare') {
    Push-Location $RepoRoot
    try {
        $Archive = Join-Path $RunRoot 'source.zip'
        if (-not (Test-Path -LiteralPath $Source)) {
            $Step = Invoke-Logged 'archive' 'git' @('-c', "safe.directory=$GitRoot", 'archive', '--format=zip', "--output=$Archive", $State.revision)
            if ($Step.exit_code -ne 0) { exit $Step.exit_code }
            Expand-Archive -LiteralPath $Archive -DestinationPath $Source
            $State.source_archive_sha256 = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
            Write-Json $StatePath $State
        } elseif ((Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $State.source_archive_sha256) {
            throw 'Existing source archive changed; use a fresh evidence directory.'
        }
        $Step = Invoke-Logged 'venv' $PythonExecutable @('-m', 'venv', $Venv)
        if ($Step.exit_code -ne 0) { exit $Step.exit_code }
        $Probe = "import sys, platform, json; print(json.dumps({'python':sys.version,'implementation':platform.python_implementation(),'os':platform.system(),'os_release':platform.release(),'os_version':platform.version(),'architecture':platform.machine(),'isolated_venv':sys.prefix != sys.base_prefix,'executable':'<venv>/Scripts/python.exe'}))"
        $Step = Invoke-Logged 'python-info' $VenvPython @('-c', $Probe)
        if ($Step.exit_code -ne 0) { exit $Step.exit_code }
    } finally { Pop-Location }
}

if ($Stage -eq 'install') {
    Push-Location $Source
    try {
        $ReadRequirements = "import tomllib,json; p=tomllib.load(open('pyproject.toml','rb'))['project']; print(json.dumps(p['dependencies']+p['optional-dependencies']['dev']))"
        $Step = Invoke-Logged 'requirements' $VenvPython @('-c', $ReadRequirements)
        if ($Step.exit_code -ne 0) { exit $Step.exit_code }
        $Requirements = @(Get-Content -LiteralPath (Join-Path $PSScriptRoot $Step.output) -Raw | ConvertFrom-Json)
        $Step = Invoke-Logged 'pip-install' $VenvPython (@('-m', 'pip', '--isolated', 'install', '--disable-pip-version-check', '--no-input', '--index-url', 'https://pypi.org/simple', '--cache-dir', (Join-Path $RunRoot 'pip-cache')) + $Requirements)
        if ($Step.exit_code -ne 0) { exit $Step.exit_code }
        $Step = Invoke-Logged 'pip-check' $VenvPython @('-m', 'pip', '--isolated', 'check')
        if ($Step.exit_code -ne 0) { exit $Step.exit_code }
        $Step = Invoke-Logged 'pip-freeze' $VenvPython @('-m', 'pip', '--isolated', 'freeze', '--all')
        if ($Step.exit_code -ne 0) { exit $Step.exit_code }
    } finally { Pop-Location }
}

if ($Stage -eq 'test') {
    if (-not @($State.commands | Where-Object { $_.name -eq 'pip-check' -and $_.exit_code -eq 0 }).Count) { throw 'Successful dependency check required before testing.' }
    Push-Location $Source
    try {
        $Step = Invoke-Logged 'pytest' $VenvPython @('-m', 'pytest', '-v')
        Get-Content -LiteralPath (Join-Path $PSScriptRoot $Step.output) | Select-Object -Last 8 | Write-Host
        exit $Step.exit_code
    } finally { Pop-Location }
}
