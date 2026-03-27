@echo off
cd /d "%~dp0"

if not exist ".git" (
    git init
)

git branch -M main

git remote remove origin >nul 2>nul
git remote add origin https://github.com/T-Kawaguchi-lab/matching-teachers-with-students.git

<<<<<<< HEAD
git pull origin main --allow-unrelated-histories
git add .
git commit -m "initial commit" 2>nul
git push -u origin main
<<<<<<< HEAD
<<<<<<< HEAD
=======
echo [INFO] After push, open the GitHub Actions tab and confirm the workflow runs.
>>>>>>> 5379900 (Initial commit)
=======

>>>>>>> 8799050 (initial commit)
pause
endlocal
=======
git add -A
git commit -m "local changes before first sync" >nul 2>nul

git pull origin main --allow-unrelated-histories --rebase
if errorlevel 1 (
    echo [ERROR] git pull failed. Please resolve conflicts, then run again.
    pause
    exit /b 1
)

git push -u origin main
if errorlevel 1 (
    echo [ERROR] git push failed.
    pause
    exit /b 1
)

echo [OK] First sync completed.
pause
>>>>>>> 8820cf2 (local changes before first sync)
