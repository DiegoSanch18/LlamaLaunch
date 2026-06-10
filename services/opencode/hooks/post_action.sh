#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# Post-Action Hook — Verificación automática después de acciones
# ═══════════════════════════════════════════════════════════════════
# Inspirado en el paso "VERIFY" del bucle agéntico de Claude Code.
# Este hook se ejecuta DESPUÉS de cualquier acción de escritura/ejecución.
#
# Uso: source hooks/post_action.sh <tipo_accion> <archivo_afectado> <exit_code>
# Ejemplo: source hooks/post_action.sh "edit" "config.json" "0"
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

ACTION_TYPE="${1:-unknown}"
TARGET_FILE="${2:-unknown}"
EXIT_CODE="${3:-0}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_DIR="$(dirname "$0")/../../logs"

# Colores
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}═══════════════════════════════════════════${NC}"
echo -e "${CYAN}  POST-ACTION HOOK — Verificación${NC}"
echo -e "${CYAN}═══════════════════════════════════════════${NC}"
echo ""

# Verificar exit code
if [[ "$EXIT_CODE" != "0" ]]; then
    echo -e "${RED}  ❌ FALLO — Exit code: ${EXIT_CODE}${NC}"
    echo -e "${RED}  Acción '${ACTION_TYPE}' en '${TARGET_FILE}' falló.${NC}"
    echo -e "${YELLOW}  Recomendación: Revisar output de error y reintentar con enfoque diferente.${NC}"
    
    # Registrar fallo
    echo "${TIMESTAMP} | FAIL | ${ACTION_TYPE} | ${TARGET_FILE} | exit=${EXIT_CODE}" >> "${LOG_DIR}/action_history.log"
    exit 0
fi

echo -e "${GREEN}  ✅ ÉXITO — Acción completada${NC}"
echo -e "  Tipo:    ${ACTION_TYPE}"
echo -e "  Target:  ${TARGET_FILE}"
echo ""

# Verificaciones específicas por tipo de acción
case "$ACTION_TYPE" in
    edit|write|create)
        # Verificar que el archivo existe y tiene contenido
        if [[ -f "$TARGET_FILE" ]]; then
            FILE_SIZE=$(wc -c < "$TARGET_FILE" 2>/dev/null || echo "0")
            echo -e "  ${GREEN}Archivo verificado: ${FILE_SIZE} bytes${NC}"
            
            # Si es Python, verificar sintaxis
            if [[ "$TARGET_FILE" == *.py ]]; then
                if command -v python3 &>/dev/null; then
                    if python3 -c "import ast; ast.parse(open('${TARGET_FILE}').read())" 2>/dev/null; then
                        echo -e "  ${GREEN}Sintaxis Python: OK${NC}"
                    else
                        echo -e "  ${YELLOW}Sintaxis Python: ADVERTENCIA — posible error de sintaxis${NC}"
                    fi
                fi
            fi
            
            # Si es JSON, verificar que es válido
            if [[ "$TARGET_FILE" == *.json ]]; then
                if command -v python3 &>/dev/null; then
                    if python3 -c "import json; json.load(open('${TARGET_FILE}'))" 2>/dev/null; then
                        echo -e "  ${GREEN}JSON válido: OK${NC}"
                    else
                        echo -e "  ${RED}JSON inválido: ERROR — archivo corrupto${NC}"
                    fi
                fi
            fi
            
            # Si es Bash, verificar sintaxis
            if [[ "$TARGET_FILE" == *.sh ]]; then
                if bash -n "$TARGET_FILE" 2>/dev/null; then
                    echo -e "  ${GREEN}Sintaxis Bash: OK${NC}"
                else
                    echo -e "  ${YELLOW}Sintaxis Bash: ADVERTENCIA — posible error${NC}"
                fi
            fi
        else
            echo -e "  ${RED}ADVERTENCIA: Archivo no encontrado después de la acción${NC}"
        fi
        ;;
    bash|shell|exec)
        echo -e "  ${GREEN}Comando ejecutado exitosamente.${NC}"
        ;;
    git_*)
        # Mostrar estado de Git después de operaciones Git
        if git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
            echo -e "  ${CYAN}Estado Git actual:${NC}"
            git status --short 2>/dev/null | head -10
        fi
        ;;
esac

# Registrar éxito
mkdir -p "$LOG_DIR"
echo "${TIMESTAMP} | OK | ${ACTION_TYPE} | ${TARGET_FILE}" >> "${LOG_DIR}/action_history.log"

echo ""
echo -e "${GREEN}═══ Post-action hook completado ═══${NC}"
echo ""
