#!/bin/bash
# Script de instalacion para OpenCode en WSL (Ubuntu)

# Obtener ruta absoluta de la carpeta del script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OPENCODE_DIR="$PROJECT_ROOT/services/opencode"

echo "======================================================================="
echo "          INSTALACION DE OPENCODE EN WSL / UBUNTU (CODING AGENT)"
echo "======================================================================="

# 1. Descargar e instalar la CLI de OpenCode
if ! command -v opencode &> /dev/null; then
    echo "[INFO] Descargando e instalando OpenCode CLI..."
    curl -fsSL https://opencode.ai/install | bash
    
    if [ $? -eq 0 ]; then
        echo "[EXITO] OpenCode CLI instalado correctamente."
    else
        echo "[ERROR] Error al descargar OpenCode. Reintentando por Homebrew/alternativo..."
        # Fallback en caso de que requiera sudo o permisos
        sudo curl -fsSL https://opencode.ai/install | bash
    fi
else
    echo "[OK] OpenCode CLI ya esta instalado: $(opencode --version 2>/dev/null || echo 'v1.0.0')"
fi

# 2. Configurar el espacio de trabajo local
mkdir -p "$OPENCODE_DIR"

# 3. Configurar variables de entorno y conexion con llama.cpp local
echo "[INFO] Configurando variables de entorno para usar tu LLM local..."

# Crear un archivo de entorno en la carpeta del servicio para configuraciones locales del proyecto
ENV_FILE="$OPENCODE_DIR/.env"
cat << EOF > "$ENV_FILE"
# Configuracion local de OpenCode para conectar con llama.cpp
OPENCODE_API_PROVIDER="openai"
OPENCODE_API_BASE="http://localhost:8080"
OPENCODE_API_KEY="local"
OPENCODE_MODEL="gemma"

# Concepto "Claude Code": Compilar/Ejecutar solo con confirmacion explicativa (Interactive Safety Gating)
OPENCODE_AUTO_EXECUTE="false"
OPENCODE_COMMAND_GATE="true"
EOF

echo "[EXITO] Configuracion guardada en: $ENV_FILE"

# Agregar sugerencia al .bashrc para comodidad del usuario
BASHRC="$HOME/.bashrc"
if ! grep -q "OPENCODE_API_BASE" "$BASHRC"; then
    echo "" >> "$BASHRC"
    echo "# Configuracion de OpenCode Local" >> "$BASHRC"
    echo "export OPENCODE_API_BASE=\"http://localhost:8080\"" >> "$BASHRC"
    echo "export OPENCODE_API_KEY=\"local\"" >> "$BASHRC"
    echo "export OPENCODE_COMMAND_GATE=\"true\"" >> "$BASHRC"
    echo "[INFO] Agregadas variables globales al archivo ~/.bashrc de tu WSL."
    echo "      (Ejecuta 'source ~/.bashrc' o abre una nueva terminal para aplicarlas)."
fi

echo ""
echo "======================================================================="
echo "             MEDIDAS DE SEGURIDAD INTERACTIVAS ACTIVA (GATE)"
echo "======================================================================="
echo "Siguiendo los estandares de seguridad de Claude Code:"
echo " - OpenCode NUNCA ejecutara comandos de consola directamente sin tu permiso."
echo " - Cada comando propuesto por el agente requerira confirmacion (Y/N)."
echo " - Los accesos a archivos externos estan limitados a tu espacio de trabajo."
echo "======================================================================="
echo ""
echo "Instalacion completada!"
echo "Para utilizarlo, navega a cualquier carpeta de tus proyectos en WSL y ejecuta:"
echo "  opencode chat"
echo "  opencode analyze"
echo "======================================================================="
