Write-Host "=== Iniciando Despliegue de Open WebUI + SearXNG ===" -ForegroundColor Cyan

# 1. Comprobar si Docker está instalado y activo
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker no se está ejecutando o no está instalado en el PATH. Por favor encienda Docker Desktop antes de continuar."
    exit 1
}
Write-Host "-> Conectado a Docker Engine de forma exitosa." -ForegroundColor Green

# 2. Validar que los puertos 3000 y 8080 estén libres en el host
$portsToCheck = @(3000, 8080)
foreach ($port in $portsToCheck) {
    $portActive = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($portActive) {
        Write-Warning "¡El puerto $port ya está siendo utilizado por otro proceso!"
        Write-Warning "Detalle del proceso en puerto ${port}:"
        Get-Process -Id $portActive.OwningProcess | Format-Table Id, Name, Path -AutoSize
        Write-Error "Despliegue cancelado debido a colisión de puertos. Libere los puertos requeridos."
        exit 1
    }
}
Write-Host "-> Puertos 3000 y 8080 libres y verificados." -ForegroundColor Green

# 3. Generar una clave secreta segura para SearXNG
$randomBytes = New-Object Byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($randomBytes)
$secretKey = [System.Convert]::ToBase64String($randomBytes) -replace '[^a-zA-Z0-9]', ''

# 4. Inyectar la clave en settings.yml
$settingsPath = "C:\temp\AI Local\services\searxng\config\settings.yml"
if (Test-Path $settingsPath) {
    $content = Get-Content $settingsPath -Raw
    if ($content -match "CLAVE_SECRETA_SUPER_SEGURA_GENERADA_LOCALMENTE") {
        $content = $content -replace "CLAVE_SECRETA_SUPER_SEGURA_GENERADA_LOCALMENTE", $secretKey
        Set-Content $settingsPath $content
        Write-Host "-> Nueva clave secreta de SearXNG inyectada en settings.yml." -ForegroundColor Green
    } else {
        Write-Host "-> settings.yml ya contiene una clave secreta personalizada. Se conserva la existente." -ForegroundColor Yellow
    }
} else {
    Write-Error "No se encontró el archivo settings.yml en la ruta esperada: $settingsPath"
    exit 1
}

# 5. Desplegar los contenedores
Write-Host "-> Iniciando contenedores mediante Docker Compose..." -ForegroundColor Yellow
Set-Location "C:\temp\AI Local\services\searxng"
docker compose down -v --remove-orphans 2>$null # Limpiar ejecuciones previas si las hay
docker compose up -d

# 6. Diagnóstico y Estado
Write-Host "`n=== Despliegue Completado con Éxito ===" -ForegroundColor Green
Write-Host "Open WebUI disponible en: http://localhost:3000" -ForegroundColor Cyan
Write-Host "SearXNG disponible en: http://localhost:8080" -ForegroundColor Cyan
Write-Host "Compruebe el panel de administración de Open WebUI para verificar la conexión." -ForegroundColor Yellow
