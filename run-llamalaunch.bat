@echo off
setlocal
cd /d "%~dp0"
title LlamaLaunch Desktop Suite

echo ========================================================
echo   LlamaLaunch Desktop Inference Suite Launcher
echo ========================================================
echo.
echo Verificando entorno Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] No se encontro Python en el PATH del sistema.
    echo Asegurate de tener Python instalado y registrado en tus variables de entorno.
    echo.
    pause
    exit /b 1
)

echo Verificando dependencias basicas...
python -c "import webview, requests, psutil" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ADVERTENCIA] Algunas dependencias podrian no estar instaladas.
    echo Se intentara iniciar la aplicacion de todos modos...
)

echo Iniciando LlamaLaunch en el escritorio...
python llamaLauncher\app.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] La aplicacion finalizo con codigo de error %ERRORLEVEL%.
    pause
    exit /b %ERRORLEVEL%
)

exit /b 0
