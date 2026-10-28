@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0subir_funnel.ps1"
exit /b %errorlevel%
