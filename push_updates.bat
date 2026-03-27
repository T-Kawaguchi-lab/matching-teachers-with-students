@echo off
cd /d "%~dp0"
set MSG=%*
if "%MSG%"=="" set MSG=Update matching inputs and generated results
git add .
git commit -m "%MSG%"
git push origin main
pause
