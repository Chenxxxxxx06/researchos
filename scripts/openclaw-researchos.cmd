@echo off
setlocal
set "REPO_ROOT=%~dp0.."
set "RESEARCHOS_CLI=%REPO_ROOT%\apps\api\.venv\Scripts\researchos.exe"
set "PYTHONUTF8=1"
chcp 65001 >nul

if not exist "%RESEARCHOS_CLI%" (
  echo ResearchOS CLI is unavailable: %RESEARCHOS_CLI% 1>&2
  echo Install the API virtual environment before using the OpenClaw bridge. 1>&2
  exit /b 1
)

"%RESEARCHOS_CLI%" %*
exit /b %ERRORLEVEL%
