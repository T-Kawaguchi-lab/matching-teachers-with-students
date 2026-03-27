@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0select_student_excel.ps1"
pause
endlocal