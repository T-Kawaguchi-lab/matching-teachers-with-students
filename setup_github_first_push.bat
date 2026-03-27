@echo off
setlocal

cd /d "%~dp0"

git init
git branch -M main
git remote remove origin 2>nul
git remote add origin https://github.com/T-Kawaguchi-lab/matching-teachers-with-students.git

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