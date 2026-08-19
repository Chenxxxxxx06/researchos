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

echo [ResearchOS] Starting the local website...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SITE_SCRIPT%" up
if errorlevel 1 (
    echo.
    echo [ResearchOS] Startup failed. Review artifacts\site-runtime for logs.
    pause
    exit /b 1
)

echo.
echo [ResearchOS] Website is ready: http://localhost:3000/login
echo [ResearchOS] Double-click stop-site.cmd to stop all project services.
exit /b 0
