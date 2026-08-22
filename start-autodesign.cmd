@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-autodesign.ps1" %*
exit /b %errorlevel%
