@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0select_teacher_excel.ps1"
pause