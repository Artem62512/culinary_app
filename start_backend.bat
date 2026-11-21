@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
set "PYTHON=%PROJECT_ROOT%backend\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo Python environment not found: backend\.venv
  echo Run the setup commands in README.md first.
  pause
  exit /b 1
)

if not exist "%PROJECT_ROOT%backend\.env" (
  echo Missing backend\.env.
  echo Copy backend\.env.example to backend\.env and set APP_USERNAME and APP_PASSWORD.
  pause
  exit /b 1
)

pushd "%PROJECT_ROOT%backend"
"%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
set "EXIT_CODE=%ERRORLEVEL%"
popd

if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%
