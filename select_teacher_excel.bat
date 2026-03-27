@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0select_teacher_excel.ps1"
pause
endlocal