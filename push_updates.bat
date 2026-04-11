@echo off
cd /d "%~dp0"

set MSG=%*
if "%MSG%"=="" set MSG=manual update

git add -A
git commit -m "auto save before pull" >nul 2>nul

git pull origin main --rebase
if errorlevel 1 (
    echo [ERROR] git pull failed. Please resolve conflicts, then run again.
    pause
    exit /b 1
)

git add -A
git commit -m "%MSG%" >nul 2>nul

git push origin main
if errorlevel 1 (
    echo [ERROR] git push failed.
    pause
    exit /b 1
)

echo [OK] Push completed.
pause