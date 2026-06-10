#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# Pre-Action Hook — Snapshot de seguridad antes de acciones destructivas
# ═══════════════════════════════════════════════════════════════════
# Inspirado en el sistema de "blast radius assessment" filtrado de Claude Code.
# Este hook se ejecuta ANTES de cualquier acción de escritura/ejecución.
#
# Uso: source hooks/pre_action.sh <tipo_accion> <descripcion>
# Ejemplo: source hooks/pre_action.sh "edit" "Modificar config.json"
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

ACTION_TYPE="${1:-unknown}"
ACTION_DESC="${2:-Sin descripción}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_DIR="$(dirname "$0")/../../logs"

# Colores para output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}═══════════════════════════════════════════${NC}"
echo -e "${CYAN}  PRE-ACTION HOOK — Evaluación de Riesgo${NC}"
echo -e "${CYAN}═══════════════════════════════════════════${NC}"
echo ""

# Clasificar riesgo
case "$ACTION_TYPE" in
    read|grep|glob|list)
        RISK="LOW"
        RISK_COLOR="$GREEN"
        ;;
    edit|write|create)
        RISK="MEDIUM"
        RISK_COLOR="$YELLOW"
        ;;
    bash|shell|exec|delete|git_push|git_reset)
        RISK="HIGH"
        RISK_COLOR="$RED"
        ;;
    *)
        RISK="UNKNOWN"
        RISK_COLOR="$YELLOW"
        ;;
esac

echo -e "  Acción:      ${ACTION_DESC}"
echo -e "  Tipo:        ${ACTION_TYPE}"
echo -e "  Riesgo:      ${RISK_COLOR}${RISK}${NC}"
echo -e "  Timestamp:   ${TIMESTAMP}"
echo ""

# Para acciones de riesgo medio o alto, crear snapshot Git
if [[ "$RISK" == "MEDIUM" || "$RISK" == "HIGH" ]]; then
    # Verificar si estamos en un repo Git
    if git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
        # Verificar si hay cambios sin commit
        if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
            echo -e "${YELLOW}  [SNAPSHOT] Guardando estado actual con git stash...${NC}"
            STASH_MSG="pre-action-hook: ${ACTION_TYPE} — ${ACTION_DESC} — ${TIMESTAMP}"
            git stash push -m "$STASH_MSG" --include-untracked 2>/dev/null || true
            echo -e "${GREEN}  [SNAPSHOT] Estado guardado. Recuperar con: git stash pop${NC}"
        else
            echo -e "${GREEN}  [SNAPSHOT] Working tree limpio, no se necesita stash.${NC}"
        fi
    else
        echo -e "${YELLOW}  [INFO] No es un repositorio Git. Sin snapshot automático.${NC}"
    fi
fi

# Para acciones de riesgo alto, pedir confirmación
if [[ "$RISK" == "HIGH" ]]; then
    echo ""
    echo -e "${RED}  ⚠️  ACCIÓN DE ALTO RIESGO ⚠️${NC}"
    echo -e "${RED}  ¿Confirmar ejecución? (y/N):${NC}"
    read -r confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo -e "${RED}  [CANCELADO] Acción abortada por el usuario.${NC}"
        exit 1
    fi
    echo -e "${GREEN}  [CONFIRMADO] Procediendo con la acción.${NC}"
fi

# Registrar en log
mkdir -p "$LOG_DIR"
echo "${TIMESTAMP} | ${RISK} | ${ACTION_TYPE} | ${ACTION_DESC}" >> "${LOG_DIR}/action_history.log"

echo ""
echo -e "${GREEN}═══ Pre-action hook completado ═══${NC}"
echo ""
