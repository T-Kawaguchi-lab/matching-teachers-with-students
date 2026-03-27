@echo off
cd /d "%~dp0"
set MSG=%*
<<<<<<< HEAD
if "%MSG%"=="" set MSG=Update matching inputs and generated results
=======
if "%MSG%"=="" set MSG=Manual update for matching project
>>>>>>> 5379900 (Initial commit)
git add .
git commit -m "%MSG%"
git push origin main
pause
