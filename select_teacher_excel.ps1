param()

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
    Write-Host '[ERROR] Run setup_first_time.bat first.'
    exit 1
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
    $json = $Registry | ConvertTo-Json -Depth 6
    Set-Content -Path $Path -Value $json -Encoding UTF8
}

Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Filter = 'Excel Files (*.xlsx;*.xls)|*.xlsx;*.xls'
$dialog.Title = 'Select teacher Excel file'

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
