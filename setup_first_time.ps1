$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
<<<<<<< HEAD
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
<<<<<<< HEAD
pip install -r requirements.txt
=======
python -m pip install -r requirements.txt
>>>>>>> 5379900 (Initial commit)
Write-Host '[OK] Setup completed.'
=======

Write-Host '[INFO] Initial setup started.'

function Find-PythonExe {
    $candidates = @()

    # 1. PATH 上の python
    $cmdPython = Get-Command python -ErrorAction SilentlyContinue
    if ($cmdPython -and $cmdPython.Source) {
        $candidates += $cmdPython.Source
    }

    # 2. PATH 上の py launcher
    $cmdPy = Get-Command py -ErrorAction SilentlyContinue
    if ($cmdPy -and $cmdPy.Source) {
        $candidates += $cmdPy.Source
    }

    # 3. よくある Anaconda / Miniconda の場所
    $userHomeDir = $env:USERPROFILE
    $candidates += @(
        "$userHomeDir\anaconda3\python.exe",
        "$userHomeDir\Anaconda3\python.exe",
        "$userHomeDir\miniconda3\python.exe",
        "$userHomeDir\Miniconda3\python.exe",
        "C:\ProgramData\anaconda3\python.exe",
        "C:\ProgramData\Anaconda3\python.exe",
        "C:\ProgramData\miniconda3\python.exe",
        "C:\ProgramData\Miniconda3\python.exe"
    )

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not $candidate) { continue }
        if (Test-Path $candidate) {
            try {
                & $candidate --version | Out-Null
                return $candidate
            } catch {
            }
        }
    }

    return $null
}

$pythonExe = Find-PythonExe

if (-not $pythonExe) {
    Write-Host '[ERROR] Python not found.'
    Write-Host '[INFO] If you use Anaconda, set the path manually like this:'
    Write-Host '$pythonExe = "C:\Users\takum\anaconda3\python.exe"'
    exit 1
}

Write-Host "[INFO] Using Python: $pythonExe"
Write-Host '[INFO] Creating virtual environment...'

& $pythonExe -m venv .venv
if ($LASTEXITCODE -ne 0) {
    Write-Host '[ERROR] Failed to create venv.'
    exit 1
}

$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Host '[ERROR] venv python not found.'
    exit 1
}

Write-Host '[INFO] Upgrading pip...'
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    Write-Host '[ERROR] Failed to upgrade pip.'
    exit 1
}

Write-Host '[INFO] Installing requirements...'
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host '[ERROR] Failed to install requirements.'
    exit 1
}

Write-Host '[OK] Setup completed successfully.'
>>>>>>> 8799050 (initial commit)
