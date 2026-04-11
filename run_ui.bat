@echo off
cd /d "%~dp0"

set APP_URL=

REM .env から読み込み
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /I "%%A"=="STREAMLIT_APP_URL" set APP_URL=%%B
  )
)

REM なければ example から
if "%APP_URL%"=="" (
  if exist ".env.example" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env.example") do (
      if /I "%%A"=="STREAMLIT_APP_URL" set APP_URL=%%B
    )
  )
)

REM URL がちゃんと設定されていれば開く
if not "%APP_URL%"=="" (
  echo %APP_URL% | findstr /C:"ここに入れる" >nul
  if errorlevel 1 (
    start "" "%APP_URL%"
    exit /b 0
  )
)

REM ローカル起動
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Run setup_first_time.bat first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m streamlit run streamlit_app.py
pause