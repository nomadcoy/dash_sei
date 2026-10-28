@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0subir_dash.ps1"
exit /b %errorlevel%