#!/usr/bin/env python3
"""
Context Compactor — Compactación de Contexto por Capas
=====================================================
Implementa el sistema de 3 capas revelado en la filtración de Claude Code (marzo 2026):
- Tier 1: Session Memory — preserva memoria estructurada persistente
- Tier 2: Microcompact — limpia ruido (outputs largos, base64, bloques repetidos)
- Tier 3: Summarization — genera resumen comprimido vía modelo local

Uso:
    python context-compactor.py --input chat_history.json --budget 6000 --api http://localhost:8080
    python context-compactor.py --input chat_history.json --tier 2  # Solo microcompact
    cat messages.json | python context-compactor.py --budget 4000   # Via stdin
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("ERROR: Requiere 'requests'. Instalar con: pip install requests")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
DEFAULT_API_BASE = "http://localhost:8080"
DEFAULT_TOKEN_BUDGET = 6000  # tokens reservados para conversación
SYSTEM_PROMPT_RESERVE = 1500  # tokens reservados para system prompt + docs/PROJECT.md

# Patrones de ruido para Tier 2
NOISE_PATTERNS = [
    # Base64 largo (imágenes, binarios)
    (r'data:image/[^;]+;base64,[A-Za-z0-9+/=]{100,}', '[IMAGEN_BASE64_ELIMINADA]'),
    # Outputs de terminal muy largos (>50 líneas)
    (r'```(?:bash|shell|terminal|output)?\n(?:.*\n){50,}```', '```\n[OUTPUT_TRUNCADO: >50 líneas eliminadas. Solo las últimas 10 líneas preservadas]\n```'),
    # Stack traces repetitivos
    (r'(Traceback \(most recent call last\):.*?)(?=\n\n|\Z)', lambda m: m.group()[:500] + '\n[STACK_TRACE_TRUNCADO]' if len(m.group()) > 500 else m.group()),
    # Bloques de código duplicados exactos (placeholder)
    (r'```(\w+)?\n(.{500,}?)```', lambda m: m.group() if len(m.group()) < 2000 else f'```{m.group(1) or ""}\n[BLOQUE_CODIGO_LARGO: {len(m.group(2))} chars truncado]\n```'),
    # JSON dumps enormes
    (r'\{[^{}]{3000,}\}', '[JSON_GRANDE_ELIMINADO]'),
    # Paths de archivo repetidos
    (r'((?:/[\w.-]+){4,}/[\w.-]+(?:\n|$)){10,}', '[LISTA_ARCHIVOS_TRUNCADA]\n'),
]


def estimate_tokens(text: str) -> int:
    """Estimación rápida de tokens (1 token ≈ 4 caracteres para español/código)."""
    return len(text) // 4


def fetch_server_n_ctx(api_base: str) -> Optional[int]:
    """Queries llama-server's /props or /slots endpoint to dynamically discover n_ctx."""
    try:
        # llama-server exposes properties at /props
        response = requests.get(f"{api_base}/props", timeout=1.5)
        if response.status_code == 200:
            data = response.json()
            if "n_ctx" in data:
                return int(data["n_ctx"])
    except Exception:
        pass
    return None


def tier1_session_memory(messages: list, memory_file: Optional[Path] = None) -> list:
    """
    Tier 1: Session Memory
    Preserva la memoria persistente y los mensajes más recientes.
    Elimina mensajes antiguos manteniendo los últimos N y el contexto del sistema.
    """
    if not messages:
        return messages

    # Separar mensajes del sistema de los del usuario/asistente
    system_msgs = [m for m in messages if m.get('role') == 'system']
    conversation = [m for m in messages if m.get('role') != 'system']

    # Si hay archivo de memoria, inyectarlo como contexto del sistema
    memory_content = ""
    if memory_file and memory_file.exists():
        memory_content = memory_file.read_text(encoding='utf-8')
        memory_msg = {
            'role': 'system',
            'content': f"[MEMORIA_PERSISTENTE]\n{memory_content}\n[/MEMORIA_PERSISTENTE]"
        }
        system_msgs = [memory_msg] + system_msgs

    # Preservar los últimos 10 mensajes + el primero (objetivo original)
    if len(conversation) > 12:
        preserved = conversation[:2] + conversation[-10:]
        dropped_count = len(conversation) - 12
        separator = {
            'role': 'system',
            'content': f'[CONTEXTO_COMPACTADO: {dropped_count} mensajes anteriores omitidos por límite de ventana]'
        }
        conversation = [preserved[0], preserved[1], separator] + preserved[2:]

    return system_msgs + conversation


def tier2_microcompact(messages: list) -> list:
    """
    Tier 2: Microcompact (Reducción de Ruido)
    Limpia outputs de herramientas grandes, base64, y bloques repetitivos.
    """
    compacted = []
    for msg in messages:
        content = msg.get('content', '')
        if not isinstance(content, str):
            compacted.append(msg)
            continue

        # Aplicar patrones de limpieza
        cleaned = content
        for pattern, replacement in NOISE_PATTERNS:
            if callable(replacement):
                cleaned = re.sub(pattern, replacement, cleaned, flags=re.DOTALL)
            else:
                cleaned = re.sub(pattern, replacement, cleaned, flags=re.DOTALL)

        # Eliminar líneas en blanco excesivas
        cleaned = re.sub(r'\n{4,}', '\n\n\n', cleaned)

        compacted.append({**msg, 'content': cleaned})

    return compacted


def tier3_summarize(messages: list, api_base: str, token_budget: int) -> list:
    """
    Tier 3: Summarization
    Genera un resumen comprimido de la conversación vía modelo local.
    """
    current_tokens = sum(estimate_tokens(m.get('content', '')) for m in messages)

    if current_tokens <= token_budget:
        return messages  # Ya cabe, no necesita resumen

    # Separar sistema de conversación
    system_msgs = [m for m in messages if m.get('role') == 'system']
    conversation = [m for m in messages if m.get('role') != 'system']

    if len(conversation) <= 4:
        return messages  # Muy pocos mensajes para resumir

    # Tomar los mensajes a resumir (todos menos los últimos 4)
    to_summarize = conversation[:-4]
    to_keep = conversation[-4:]

    # Construir el texto a resumir
    summary_input = "\n".join([
        f"[{m.get('role', 'unknown').upper()}]: {m.get('content', '')[:1000]}"
        for m in to_summarize
    ])

    # Llamar al modelo local para generar resumen
    summary_prompt = f"""Resume la siguiente conversación en un párrafo conciso y estructurado.
Preserva: objetivos principales, decisiones tomadas, archivos modificados, errores encontrados.
Elimina: saludos, confirmaciones triviales, outputs de herramientas repetitivos.
Máximo 300 palabras.

CONVERSACIÓN A RESUMIR:
{summary_input}

RESUMEN ESTRUCTURADO:"""

    try:
        response = requests.post(
            f"{api_base}/v1/chat/completions",
            json={
                "model": "local",
                "messages": [{"role": "user", "content": summary_prompt}],
                "max_tokens": 500,
                "temperature": 0.3
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        summary_text = result['choices'][0]['message']['content']
    except Exception as e:
        # Fallback: resumen mecánico sin LLM
        summary_text = f"[Resumen automático de {len(to_summarize)} mensajes — Error al contactar modelo: {e}]\n"
        summary_text += "\n".join([
            f"- [{m.get('role')}]: {m.get('content', '')[:150]}..."
            for m in to_summarize[:5]
        ])

    summary_msg = {
        'role': 'system',
        'content': f'[RESUMEN_SESIÓN_ANTERIOR]\n{summary_text}\n[/RESUMEN_SESIÓN_ANTERIOR]'
    }

    return system_msgs + [summary_msg] + to_keep


def compact(messages: list, tier: int = 3, token_budget: int = DEFAULT_TOKEN_BUDGET,
            api_base: str = DEFAULT_API_BASE, memory_file: Optional[Path] = None) -> list:
    """
    Pipeline de compactación completo.
    tier=1: Solo Session Memory
    tier=2: Session Memory + Microcompact
    tier=3: Todas las capas
    """
    result = messages

    # 1. Intentar descubrir dinámicamente el n_ctx del servidor local
    server_n_ctx = fetch_server_n_ctx(api_base)
    if server_n_ctx is not None:
        # Reservar un búfer seguro para la generación de tokens de salida (ej. 2048 tokens)
        output_buffer = 2048
        resolved_budget = server_n_ctx - output_buffer
        print(f"[INFO] Server context detected dynamically: {server_n_ctx} tokens. Set dynamic input budget to {resolved_budget} tokens.", file=sys.stderr)
        token_budget = resolved_budget
    else:
        print(f"[WARN] Local server props not reachable. Using static token budget: {token_budget} tokens.", file=sys.stderr)

    # Tier 1: Session Memory
    result = tier1_session_memory(result, memory_file)

    if tier >= 2:
        # Tier 2: Microcompact (Regex cleanup of huge console outputs, base64, etc.)
        result = tier2_microcompact(result)

    if tier >= 3:
        # Tier 3: Summarization
        result = tier3_summarize(result, api_base, token_budget)

    # 2. Bucle de verificación de seguridad agresivo contra desbordamiento de contexto (OOM Fail-Safe)
    post_tokens = sum(estimate_tokens(m.get('content', '')) for m in result)
    if post_tokens > token_budget:
        print(f"[WARN] Context size ({post_tokens}) still exceeds dynamic budget ({token_budget}) after summarization. Applying OOM Fail-Safe...", file=sys.stderr)
        
        system_msgs = [m for m in result if m.get('role') == 'system']
        conversation = [m for m in result if m.get('role') != 'system']
        
        # Recortar agresivamente: mantener SOLO el system prompt base y el ÚLTIMO mensaje (pregunta actual)
        if conversation:
            result = system_msgs + [conversation[-1]]
            new_tokens = sum(estimate_tokens(m.get('content', '')) for m in result)
            print(f"[SUCCESS] OOM Fail-Safe active. Truncated history to last message only. Context size reduced to {new_tokens} tokens.", file=sys.stderr)
        
    return result



def main():
    parser = argparse.ArgumentParser(
        description='Context Compactor — Compactación de contexto por capas (Claude Code pattern)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--input', '-i', type=str, help='Archivo JSON con historial de chat')
    parser.add_argument('--output', '-o', type=str, help='Archivo de salida (default: stdout)')
    parser.add_argument('--budget', '-b', type=int, default=DEFAULT_TOKEN_BUDGET,
                        help=f'Presupuesto de tokens para conversación (default: {DEFAULT_TOKEN_BUDGET})')
    parser.add_argument('--tier', '-t', type=int, default=3, choices=[1, 2, 3],
                        help='Nivel máximo de compactación (1=memory, 2=+microcompact, 3=+summarize)')
    parser.add_argument('--api', type=str, default=DEFAULT_API_BASE,
                        help=f'URL base del servidor de inferencia (default: {DEFAULT_API_BASE})')
    parser.add_argument('--memory', '-m', type=str,
                        help='Path al archivo de memoria persistente (docs/PROJECT.md)')
    parser.add_argument('--stats', action='store_true',
                        help='Mostrar estadísticas de compactación')

    args = parser.parse_args()

    # Leer input
    if args.input:
        with open(args.input, 'r', encoding='utf-8') as f:
            messages = json.load(f)
    elif not sys.stdin.isatty():
        messages = json.load(sys.stdin)
    else:
        parser.error("Proporciona --input o envía JSON por stdin")

    # Asegurar que es una lista de mensajes
    if isinstance(messages, dict) and 'messages' in messages:
        messages = messages['messages']

    memory_file = Path(args.memory) if args.memory else None

    # Estadísticas pre-compactación
    pre_tokens = sum(estimate_tokens(m.get('content', '')) for m in messages)
    pre_count = len(messages)

    # Ejecutar compactación
    result = compact(messages, tier=args.tier, token_budget=args.budget,
                     api_base=args.api, memory_file=memory_file)

    # Estadísticas post-compactación
    post_tokens = sum(estimate_tokens(m.get('content', '')) for m in result)
    post_count = len(result)

    if args.stats:
        reduction = ((pre_tokens - post_tokens) / pre_tokens * 100) if pre_tokens > 0 else 0
        stats = {
            'pre': {'messages': pre_count, 'tokens_est': pre_tokens},
            'post': {'messages': post_count, 'tokens_est': post_tokens},
            'reduction_pct': round(reduction, 1),
            'tier_applied': args.tier
        }
        print(json.dumps(stats, indent=2), file=sys.stderr)

    # Output
    output_data = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_data)
        print(f"Compactado: {pre_tokens} → {post_tokens} tokens ({post_count} msgs) → {args.output}",
              file=sys.stderr)
    else:
        print(output_data)


if __name__ == '__main__':
    main()
