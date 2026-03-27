param()

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Load-KeyValueFile {
    param([string]$Path)
    $values = @{}
    if (-not (Test-Path $Path)) { return $values }
    foreach ($line in Get-Content $Path) {
        if ($line -match '^\s*#') { continue }
        if ($line -notmatch '=') { continue }
        $parts = $line -split '=', 2
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        if ($key) { $values[$key] = $value }
    }
    return $values
}

function Load-Registry {
    param([string]$Path)
    if (Test-Path $Path) {
        try { return (Get-Content $Path -Raw | ConvertFrom-Json -AsHashtable) }
        catch { return @{} }
    }
    return @{}
}

function Save-Registry {
    param([hashtable]$Registry, [string]$Path)
    $Registry | ConvertTo-Json -Depth 8 | Set-Content -Path $Path -Encoding UTF8
}

function Ensure-GitRepository {
    if (-not (Test-Path (Join-Path $PSScriptRoot '.git'))) {
        Write-Host '[ERROR] Git repository not found.'
        exit 1
    }
}

function Get-VenvPython {
    $venvPathFile = Join-Path $PSScriptRoot 'venv_path.txt'
    if (-not (Test-Path $venvPathFile)) {
        Write-Host '[ERROR] venv_path.txt not found. Run setup_first_time.bat first.'
        exit 1
    }

    $venvRoot = (Get-Content $venvPathFile -Raw).Trim()
    $venvPython = Join-Path $venvRoot 'Scripts\python.exe'

    if (-not (Test-Path $venvPython)) {
        Write-Host '[ERROR] venv python not found.'
        exit 1
    }

    return $venvPython
}

function Git-Run {
    param([string[]]$Args, [bool]$AllowFail = $false)
    & git @Args
    $code = $LASTEXITCODE
    if ((-not $AllowFail) -and $code -ne 0) {
        Write-Host "[ERROR] git command failed: git $($Args -join ' ')"
        exit 1
    }
    return $code
}

function PreSync-LocalChanges {
    Write-Host '[INFO] Saving local changes before pull...'
    Git-Run -Args @('add','-A')
    Git-Run -Args @('commit','-m','auto save before pull') -AllowFail $true | Out-Null
}

function Pull-Latest {
    Write-Host '[INFO] Pulling latest main...'
    Git-Run -Args @('pull','origin','main','--rebase')
}

function Run-LocalPipelineCheck {
    $venvPython = Get-VenvPython
    Write-Host '[INFO] Checking local environment...'
    & $venvPython -c "import pandas, sklearn, streamlit; print('python env ok')"
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[ERROR] Python environment check failed.'
        exit 1
    }
}

function Push-Changes {
    param([string]$CommitMessage)

    Git-Run -Args @('add','incoming/teachers_latest.xlsx','incoming/input_registry.json')
    Git-Run -Args @('commit','-m',$CommitMessage) -AllowFail $true | Out-Null
    Git-Run -Args @('push','origin','main')

    Write-Host '[OK] Push completed.'
}

function Open-PostPushPages {
    $envPath = Join-Path $PSScriptRoot '.env'
    if (-not (Test-Path $envPath)) { $envPath = Join-Path $PSScriptRoot '.env.example' }
    $envMap = Load-KeyValueFile -Path $envPath

    if ($envMap.ContainsKey('GITHUB_ACTIONS_URL') -and $envMap['GITHUB_ACTIONS_URL'] -and $envMap['GITHUB_ACTIONS_URL'] -notmatch 'ここに入れる') {
        Start-Process $envMap['GITHUB_ACTIONS_URL']
    }

    if ($envMap.ContainsKey('STREAMLIT_APP_URL') -and $envMap['STREAMLIT_APP_URL'] -and $envMap['STREAMLIT_APP_URL'] -notmatch 'ここに入れる') {
        Start-Process $envMap['STREAMLIT_APP_URL']
    }
}

Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Filter = 'Excel Files (*.xlsx;*.xls)|*.xlsx;*.xls'
$dialog.Title = 'Select teacher Excel file'

if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
    Write-Host '[INFO] Selection cancelled.'
    exit 0
}

Ensure-GitRepository
Run-LocalPipelineCheck
PreSync-LocalChanges
Pull-Latest

$incomingDir = Join-Path $PSScriptRoot 'incoming'
if (-not (Test-Path $incomingDir)) {
    New-Item -ItemType Directory -Path $incomingDir | Out-Null
}

$target = Join-Path $incomingDir 'teachers_latest.xlsx'
Copy-Item $dialog.FileName $target -Force
Write-Host "[OK] Saved teacher Excel: $target"

$registryPath = Join-Path $incomingDir 'input_registry.json'
$registry = Load-Registry -Path $registryPath
$registry['teacher_input'] = @{
    original_path = $dialog.FileName
    stored_path   = $target
    updated_at    = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    workflow      = 'auto_commit_then_pull_then_push'
}
$registry['last_local_action'] = 'teacher_excel_updated_and_pushed'
Save-Registry -Registry $registry -Path $registryPath

$timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Push-Changes -CommitMessage "Update teacher input [$timestamp]"

Open-PostPushPages