param()

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

<<<<<<< HEAD
$pythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
    Write-Host '[ERROR] Run setup_first_time.bat first.'
    exit 1
=======
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
>>>>>>> 5379900 (Initial commit)
}

function Load-Registry {
    param([string]$Path)
    if (Test-Path $Path) {
        try {
            return (Get-Content $Path -Raw | ConvertFrom-Json -AsHashtable)
        } catch {
            return @{}
        }
    }
    return @{}
}

function Save-Registry {
    param([hashtable]$Registry, [string]$Path)
<<<<<<< HEAD
    $json = $Registry | ConvertTo-Json -Depth 6
    Set-Content -Path $Path -Value $json -Encoding UTF8
}

=======
    $json = $Registry | ConvertTo-Json -Depth 8
    Set-Content -Path $Path -Value $json -Encoding UTF8
}

function Ensure-GitRepository {
    if (-not (Test-Path (Join-Path $PSScriptRoot '.git'))) {
        Write-Host '[ERROR] Git repository not found. Run setup_github_first_push.bat first.'
        exit 1
    }
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

>>>>>>> 5379900 (Initial commit)
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Filter = 'Excel Files (*.xlsx;*.xls)|*.xlsx;*.xls'
$dialog.Title = 'Select teacher Excel file'

<<<<<<< HEAD
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    $target = Join-Path $PSScriptRoot 'incoming\teachers_latest.xlsx'
    Copy-Item $dialog.FileName $target -Force
    Write-Host "[OK] Saved teacher Excel: $target"

    $student = Join-Path $PSScriptRoot 'incoming\students_latest.xlsx'
    $registryPath = Join-Path $PSScriptRoot 'incoming\input_registry.json'
    $registry = Load-Registry -Path $registryPath
    $registry['teacher_input'] = @{
        original_path = $dialog.FileName
        stored_path = $target
        updated_at = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    }

    if (Test-Path $student) {
        $registry['pipeline_behavior'] = 'teacher updated; student latest reused for scoring'
        Save-Registry -Registry $registry -Path $registryPath
        Write-Host '[INFO] Reusing previous student latest file and running scoring.'
        & $pythonExe -m committee_matching.pipeline
    } else {
        $registry['pipeline_behavior'] = 'teacher updated only; waiting for first student file'
        Save-Registry -Registry $registry -Path $registryPath
        Write-Host '[INFO] No student Excel yet. Run select_student_excel.bat next.'
    }
}
=======
if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
    Write-Host '[INFO] Selection cancelled.'
    exit 0
}

Ensure-GitRepository

$target = Join-Path $PSScriptRoot 'incoming\teachers_latest.xlsx'
Copy-Item $dialog.FileName $target -Force
Write-Host "[OK] Saved Excel: $target"

$registryPath = Join-Path $PSScriptRoot 'incoming\input_registry.json'
$registry = Load-Registry -Path $registryPath
$registry['teacher_input'] = @{
    original_path = $dialog.FileName
    stored_path = $target
    updated_at = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    workflow = 'commit_and_push_then_github_actions_auto_process'
}
$registry['last_local_action'] = 'teacher_excel_updated_and_pushed'
Save-Registry -Registry $registry -Path $registryPath

git add incoming\teachers_latest.xlsx incoming/input_registry.json
if ($LASTEXITCODE -ne 0) {
    Write-Host '[ERROR] git add failed.'
    exit 1
}

$timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
git commit -m "Update teacher input [$timestamp]"
if ($LASTEXITCODE -ne 0) {
    Write-Host '[INFO] No new changes to commit.'
} else {
    git push origin main
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[ERROR] git push failed.'
        exit 1
    }
    Write-Host '[OK] Push completed. GitHub Actions will process the new input.'
}

Open-PostPushPages
Write-Host '[INFO] Opened GitHub Actions and Streamlit Cloud if URLs were configured.'
>>>>>>> 5379900 (Initial commit)
