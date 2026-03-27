@echo off
cd /d "%~dp0"
if not exist ".git" git init
git branch -M main
git remote remove origin >nul 2>nul
git remote add origin https://github.com/T-Kawaguchi-lab/matching-teachers-with-students.git
git add .
git commit -m "Initial commit"
git push -u origin main
<<<<<<< HEAD
=======
echo [INFO] After push, open the GitHub Actions tab and confirm the workflow runs.
>>>>>>> 5379900 (Initial commit)
pause
