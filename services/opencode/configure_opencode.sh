#!/bin/bash
# Script para configurar OpenCode con la IP dinámica del Host Windows en WSL

echo "======================================================================="
echo "        CONFIGURANDO RESOLUCION DE IP DINAMICA EN WSL"
echo "======================================================================="

BASHRC="$HOME/.bashrc"
CONFIG_FILE="$HOME/.config/opencode/opencode.json"
AUTH_FILE="$HOME/.local/share/opencode/auth.json"

# 1. Limpiar declaraciones previas en ~/.bashrc
sed -i '/# Configuración de OpenCode Local/d' "$BASHRC"
sed -i '/export OPENCODE_API_BASE/d' "$BASHRC"
sed -i '/export OPENCODE_API_KEY/d' "$BASHRC"
sed -i '/export OPENCODE_COMMAND_GATE/d' "$BASHRC"

# 2. Agregar la nueva declaración dinámica a ~/.bashrc
cat << 'EOF' >> "$BASHRC"

# Configuración de OpenCode Local
export OPENCODE_API_BASE="http://$(ip route | grep default | awk '{print $3}'):8080/v1"
export OPENCODE_API_KEY="local"
export OPENCODE_COMMAND_GATE="true"
EOF

echo "[OK] ~/.bashrc actualizado con IP dinámica."

# 3. Crear directorios de configuración de OpenCode si no existen
mkdir -p "$HOME/.config/opencode"
mkdir -p "$HOME/.local/share/opencode"

# 4. Escribir ~/.config/opencode/opencode.json utilizando la variable de entorno
cat << 'EOF' > "$CONFIG_FILE"
{
  "provider": {
    "llama-cpp": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Llama.cpp Local Server",
      "options": {
        "baseURL": "{env:OPENCODE_API_BASE}"
      },
      "models": {
        "gemma": {},
        "llama": {},
        "qwen": {}
      }
    }
  }
}
EOF

echo "[OK] Configuración global guardada en: $CONFIG_FILE"

# 5. Escribir ~/.local/share/opencode/auth.json
cat << 'EOF' > "$AUTH_FILE"
{
  "llama-cpp": {
    "token": "local"
  }
}
EOF

echo "[OK] Credenciales globales guardadas en: $AUTH_FILE"
echo "======================================================================="
echo "¡Configuración completada con éxito!"
echo "Por favor ejecuta en tu terminal de WSL:"
echo "  source ~/.bashrc"
echo "Y luego inicia de nuevo opencode con:"
echo "  opencode"
echo "======================================================================="
