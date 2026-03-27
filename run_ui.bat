@echo off
cd /d "%~dp0"
<<<<<<< HEAD
=======
set APP_URL=
if exist ".env" (
  for /f "tokens=1,* delims==" %%A in (.env) do (
    if /I "%%A"=="STREAMLIT_APP_URL" set APP_URL=%%B
  )
)
if "%APP_URL%"=="" (
  if exist ".env.example" (
    for /f "tokens=1,* delims==" %%A in (.env.example) do (
      if /I "%%A"=="STREAMLIT_APP_URL" set APP_URL=%%B
    )
  )
)
if not "%APP_URL%"=="" (
  echo %APP_URL% | findstr /C:"ここに入れる" >nul
  if errorlevel 1 (
    start "" "%APP_URL%"
    exit /b 0
  )
)
>>>>>>> 5379900 (Initial commit)
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Run setup_first_time.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m streamlit run streamlit_app.py
pause
