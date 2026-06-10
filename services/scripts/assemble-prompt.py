#!/usr/bin/env python3
"""
Prompt Assembler — Ensamblador de System Prompts Modulares
==========================================================
Implementa el ensamblaje dinámico de system prompts revelado en la filtración
de Claude Code (marzo 2026). Combina fragmentos de prompts según el modo
de operación seleccionado.

Uso:
    python assemble-prompt.py --mode code
    python assemble-prompt.py --mode plan --include tool_rules
    python assemble-prompt.py --mode explore --memory ../../docs/PROJECT.md
    python assemble-prompt.py --list  # Ver fragmentos disponibles

Modos disponibles: plan, code, explore, full
"""

import argparse
import sys
from pathlib import Path

# Directorio base de los fragmentos de prompts
SCRIPT_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = SCRIPT_DIR.parent / "open-webui" / "prompts"
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# Definición de qué fragmentos se incluyen en cada modo
MODE_FRAGMENTS = {
    "plan": ["core_identity.md", "mode_plan.md", "tool_rules.md"],
    "code": ["core_identity.md", "mode_code.md", "tool_rules.md", "agentic_loop.md"],
    "explore": ["core_identity.md", "mode_explore.md", "tool_rules.md"],
    "full": ["core_identity.md", "mode_code.md", "mode_plan.md", "mode_explore.md",
             "tool_rules.md", "agentic_loop.md"],
}


def estimate_tokens(text: str) -> int:
    """Estimación rápida de tokens."""
    return len(text) // 4


def load_fragment(name: str) -> str:
    """Carga un fragmento de prompt desde el directorio de prompts."""
    path = PROMPTS_DIR / name
    if not path.exists():
        print(f"WARN: Fragmento no encontrado: {path}", file=sys.stderr)
        return ""
    return path.read_text(encoding='utf-8').strip()


def load_memory(memory_path: str) -> str:
    """Carga el archivo de memoria persistente."""
    path = Path(memory_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        print(f"WARN: Archivo de memoria no encontrado: {path}", file=sys.stderr)
        return ""
    return path.read_text(encoding='utf-8').strip()


def assemble(mode: str, include_extra: list = None, memory_path: str = None,
             exclude: list = None) -> str:
    """
    Ensambla el system prompt final combinando fragmentos según el modo.
    
    Args:
        mode: Modo de operación (plan, code, explore, full)
        include_extra: Fragmentos adicionales a incluir
        memory_path: Path al archivo de memoria persistente
        exclude: Fragmentos a excluir
    
    Returns:
        System prompt ensamblado como string
    """
    if mode not in MODE_FRAGMENTS:
        print(f"ERROR: Modo '{mode}' no reconocido. Disponibles: {list(MODE_FRAGMENTS.keys())}",
              file=sys.stderr)
        sys.exit(1)

    # Determinar fragmentos a cargar
    fragments = list(MODE_FRAGMENTS[mode])

    # Añadir extras
    if include_extra:
        for extra in include_extra:
            if not extra.endswith('.md'):
                extra += '.md'
            if extra not in fragments:
                fragments.append(extra)

    # Excluir
    if exclude:
        fragments = [f for f in fragments if f.replace('.md', '') not in exclude
                     and f not in exclude]

    # Ensamblar
    parts = []

    # 1. Memoria persistente (si existe)
    if memory_path:
        memory = load_memory(memory_path)
        if memory:
            parts.append(f"<project_memory>\n{memory}\n</project_memory>")

    # 2. Fragmentos de prompt en orden
    for frag_name in fragments:
        content = load_fragment(frag_name)
        if content:
            parts.append(content)

    # 3. Separador de modo activo
    parts.append(f"\n---\n[MODO_ACTIVO: {mode.upper()}]\n")

    return "\n\n---\n\n".join(parts)


def list_fragments():
    """Lista todos los fragmentos disponibles."""
    if not PROMPTS_DIR.exists():
        print(f"Directorio de prompts no encontrado: {PROMPTS_DIR}")
        return

    print("Fragmentos disponibles:")
    print(f"  Directorio: {PROMPTS_DIR}\n")

    for f in sorted(PROMPTS_DIR.glob("*.md")):
        content = f.read_text(encoding='utf-8')
        tokens = estimate_tokens(content)
        first_line = content.split('\n')[0].strip('# ').strip()
        print(f"  {f.name:<25} {tokens:>5} tokens  — {first_line}")

    print(f"\nModos disponibles:")
    for mode, frags in MODE_FRAGMENTS.items():
        total = sum(estimate_tokens(load_fragment(f)) for f in frags)
        print(f"  {mode:<10} {total:>5} tokens  — {', '.join(frags)}")


def main():
    # Configurar salida estándar para soportar UTF-8 en Windows y evitar UnicodeEncodeError
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(
        description='Prompt Assembler — Ensamblaje dinámico de system prompts (Claude Code pattern)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--mode', '-m', type=str, choices=list(MODE_FRAGMENTS.keys()),
                        help='Modo de operación')
    parser.add_argument('--include', '-i', nargs='+', default=[],
                        help='Fragmentos adicionales a incluir')
    parser.add_argument('--exclude', '-e', nargs='+', default=[],
                        help='Fragmentos a excluir')
    parser.add_argument('--memory', type=str,
                        help='Path al archivo de memoria persistente (docs/PROJECT.md)')
    parser.add_argument('--list', '-l', action='store_true',
                        help='Listar fragmentos disponibles')
    parser.add_argument('--output', '-o', type=str,
                        help='Archivo de salida (default: stdout)')
    parser.add_argument('--stats', action='store_true',
                        help='Mostrar estadísticas de tokens')
    parser.add_argument('--copy', action='store_true',
                        help='Copiar al portapapeles (requiere pyperclip)')

    args = parser.parse_args()

    if args.list:
        list_fragments()
        return

    if not args.mode:
        parser.error("Especifica --mode o usa --list para ver opciones")

    result = assemble(args.mode, include_extra=args.include,
                      memory_path=args.memory, exclude=args.exclude)

    if args.stats:
        tokens = estimate_tokens(result)
        print(f"Tokens estimados: {tokens}", file=sys.stderr)
        print(f"Modo: {args.mode}", file=sys.stderr)
        print(f"Fragmentos incluidos: {MODE_FRAGMENTS[args.mode]}", file=sys.stderr)

    if args.output:
        Path(args.output).write_text(result, encoding='utf-8')
        print(f"Prompt ensamblado guardado en: {args.output}", file=sys.stderr)
    elif args.copy:
        try:
            import pyperclip
            pyperclip.copy(result)
            print("Prompt copiado al portapapeles", file=sys.stderr)
        except ImportError:
            print("ERROR: pyperclip no instalado. Usa: pip install pyperclip", file=sys.stderr)
            print(result)
    else:
        print(result)


if __name__ == '__main__':
    main()
