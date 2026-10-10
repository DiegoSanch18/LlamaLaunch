# ==============================================================================
# LlamaLaunch Docker Suite — Script de Despliegue Desacoplado
# ==============================================================================

Write-Host ">>> [1/4] Verificando montura de G:\ en Docker Desktop (WSL2)..." -ForegroundColor Cyan
try {
    wsl -d docker-desktop -u root mount -t drvfs G: /mnt/host/g 2>$null
    Write-Host "    [OK] Montura /mnt/host/g verificada para 'G:\My Drive\AI Local\models'." -ForegroundColor Green
} catch {
    Write-Host "    [INFO] Continuando sin remonte forzado en WSL." -ForegroundColor Yellow
}

Write-Host ">>> [2/4] Verificando red compartida con Atomic AI (atomic_ai_ai-network)..." -ForegroundColor Cyan
try {
    docker network create atomic_ai_ai-network 2>$null | Out-Null
    Write-Host "    [OK] Red 'atomic_ai_ai-network' lista." -ForegroundColor Green
} catch {
    # Ya existe
}

Write-Host ">>> [3/4] Compilando y levantando contenedores desacoplados..." -ForegroundColor Cyan
docker compose up -d --build

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host "  LLAMALAUNCH DESKTOP INFERENCE SUITE DESPLEGADA EXITOSAMENTE        " -ForegroundColor Green
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host "  - Frontend UI (Nginx)   : http://localhost:3000" -ForegroundColor White
    Write-Host "  - Backend API (Bottle)  : http://localhost:5000" -ForegroundColor White
    Write-Host "  - Inference Gateway     : http://localhost:8082" -ForegroundColor White
    Write-Host "  - Modelos Vinculados    : G:\My Drive\AI Local\models (/app/models)" -ForegroundColor White
    Write-Host "  - Interconexión         : Atomic AI Proxy (:8000) <-> Gateway" -ForegroundColor White
    Write-Host "======================================================================" -ForegroundColor Green
} else {
    Write-Host ">>> [ERROR] Ocurrió un fallo al levantar los contenedores de Docker." -ForegroundColor Red
}
