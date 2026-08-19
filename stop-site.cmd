@echo off
setlocal

rem Always run from the repository root, including when double-clicked.
cd /d "%~dp0"
set "SITE_SCRIPT=%~dp0scripts\site.ps1"

if not exist "%SITE_SCRIPT%" (
    echo [ResearchOS] Missing launcher: %SITE_SCRIPT%
    pause
    exit /b 1
)

echo [ResearchOS] Stopping the local website...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SITE_SCRIPT%" down
if errorlevel 1 (
    echo.
    echo [ResearchOS] Shutdown failed. Review artifacts\site-runtime for logs.
    pause
    exit /b 1
)

echo.
echo [ResearchOS] Website, API, worker, and infrastructure are stopped.
exit /b 0
