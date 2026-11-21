@echo off
setlocal

set "PROJECT_ROOT=%~dp0"

where node.exe >nul 2>nul
if errorlevel 1 (
  echo Node.js is required. Install Node.js 22 and retry.
  pause
  exit /b 1
)

where npm.cmd >nul 2>nul
if errorlevel 1 (
  echo npm was not found. Reinstall Node.js 22 with npm.
  pause
  exit /b 1
)

if not exist "%PROJECT_ROOT%frontend\node_modules\vite\bin\vite.js" (
  echo Frontend dependencies are missing.
  echo Run "npm ci" in the frontend folder first.
  pause
  exit /b 1
)

pushd "%PROJECT_ROOT%frontend"
call npm.cmd run dev -- --host 127.0.0.1
set "EXIT_CODE=%ERRORLEVEL%"
popd

if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%
