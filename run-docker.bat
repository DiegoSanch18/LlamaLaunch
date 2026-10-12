@echo off
chcp 65001 > nul
echo ==============================================================================
echo   LlamaLaunch Docker Suite - Despliegue Desacoplado
echo ==============================================================================

echo [1/4] Verificando montura de G:\ en Docker Desktop (WSL2)...
wsl -d docker-desktop -u root mount -t drvfs G: /mnt/host/g >nul 2>&1

echo [2/4] Verificando red compartida con Atomic AI...
docker network create atomic_ai_ai-network >nul 2>&1

echo [3/4] Levantando contenedores desacoplados con Docker Compose...
docker compose up -d --build

if %ERRORLEVEL% equ 0 (
    echo.
    echo ==============================================================================
    echo   LLAMALAUNCH DESPLEGADO EXITOSAMENTE
    echo ==============================================================================
    echo   - Frontend UI (Nginx)   : http://localhost:3000
    echo   - Backend API (Bottle)  : http://localhost:5000
    echo   - Inference Gateway     : http://localhost:8082
    echo   - Modelos Vinculados    : G:\My Drive\AI Local\models
    echo ==============================================================================
) else (
    echo [ERROR] Ocurrió un error al ejecutar docker compose.
)
pause
