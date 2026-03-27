$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
<<<<<<< HEAD
pip install -r requirements.txt
=======
python -m pip install -r requirements.txt
>>>>>>> 5379900 (Initial commit)
Write-Host '[OK] Setup completed.'
