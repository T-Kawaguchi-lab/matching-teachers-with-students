@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0select_student_excel.ps1"
pause
