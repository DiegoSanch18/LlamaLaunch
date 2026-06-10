#!/bin/bash
# Script de instalacion para OpenClaw en WSL (Ubuntu)

# Obtener ruta absoluta de la carpeta del script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OPENCLAW_DIR="$PROJECT_ROOT/services/openclaw"

echo "======================================================================="
echo "          INSTALACION DE OPENCLAW EN WSL / UBUNTU (TELEGRAM BOT)"
echo "======================================================================="

# 1. Verificar e instalar Node.js si falta
if ! command -v node &> /dev/null; then
    echo "[INFO] Node.js no esta instalado. Instalando NVM (Node Version Manager)..."
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    
    # Cargar NVM en la sesion actual
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
    
    echo "[INFO] Instalando Node.js v22..."
    nvm install 22
    nvm use 22
    nvm alias default 22
else
    NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
    if [ "$NODE_VERSION" -lt 22 ]; then
        echo "[ADVERTENCIA] Tu version de Node.js v$(node -v) es menor a la v22."
        echo "Instalando NVM para actualizar a Node.js v22..."
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        nvm install 22
        nvm use 22
    else
        echo "[OK] Node.js v$(node -v) detectado."
    fi
fi

# 2. Instalar OpenClaw CLI globalmente
echo "[INFO] Instalando OpenClaw de forma global..."
npm install -g openclaw@latest

if [ $? -eq 0 ]; then
    echo "[EXITO] OpenClaw CLI instalado correctamente."
else
    echo "[ERROR] Error al instalar OpenClaw. Reintentando con permisos amplios..."
    sudo npm install -g openclaw@latest
fi

# 3. Preparar el espacio de trabajo local
mkdir -p "$OPENCLAW_DIR"
cd "$OPENCLAW_DIR"

echo ""
echo "======================================================================="
echo "             INSTRUCCIONES PARA EL ONBOARDING INTERACTIVO"
echo "======================================================================="
echo "A continuacion se iniciara el asistente interactivo de OpenClaw."
echo "Configura los siguientes valores para enlazarlo con tu IA local:"
echo.
echo " 1. LLM Provider ➡️ Selecciona 'OpenAI-Compatible'"
echo " 2. API Base URL ➡️ Introduce: http://localhost:8080"
echo "    (WSL reenvia automaticamente 'localhost:8080' a tu Windows Host)"
echo " 3. API Key      ➡️ Introduce: local"
echo " 4. Channel      ➡️ Selecciona 'Telegram'"
echo " 5. Bot Token    ➡️ Introduce el Token de tu bot privado de Telegram"
echo "    (Consiguelo hablando con @BotFather en Telegram de forma gratuita)"
echo "======================================================================="
echo ""
read -p "Presiona ENTER para iniciar el onboarding de OpenClaw..."

# Ejecutar el onboarding
openclaw onboard --install-daemon
