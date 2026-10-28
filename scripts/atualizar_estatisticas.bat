@echo off
setlocal
cd /d "%~dp0.."

if not exist "data\logs" mkdir "data\logs"
set "LOG=data\logs\estatisticas_cli.log"
set "PY=C:\Users\x13376866\AppData\Local\Programs\Python\Python314\python.exe"

echo. >> "%LOG%"
echo ========== [%date% %time%] inicio estatisticas ========== >> "%LOG%"
"%PY%" -m extractor.main --somente-painel --estatisticas >> "%LOG%" 2>&1
echo ========== [%date% %time%] fim (codigo %errorlevel%) ========== >> "%LOG%"

exit /b %errorlevel%
