# Generador de Diagramas Mermaid (mermaidDiagramGen)

Esta skill permite a los agentes de inteligencia artificial crear diagramas de Mermaid de forma precisa y visualmente atractiva, basándose estrictamente en las especificaciones oficiales y evitando errores sintácticos comunes.

## Estructura de la Skill

La carpeta contiene:
- `SKILL.md`: El archivo principal de instrucciones que el agente lee para aprender la sintaxis avanzada de Mermaid, reglas críticas de escape y prevención de errores (como la palabra reservada `end` en minúscula).
- `README.md`: Este archivo explicativo de uso en español.

## ¿Qué puede hacer esta Skill?

El agente de IA, al tener esta skill activa, podrá diseñar diagramas impecables utilizando toda la potencia de la suite de Mermaid:
- **Diagramas de Flujo (`flowchart`)**: Con soporte para las nuevas formas de v11.3.0+ (`@{ shape: ... }`), animaciones de aristas y múltiples subgrafos.
- **Diagramas de Secuencia (`sequenceDiagram`)**: Con soporte para activaciones, auto-numeración, medias flechas avanzadas e interconexiones centrales.
- **Diagramas de Clases (`classDiagram`)**: Modelado estático estructurado con modificadores de visibilidad, genéricos (`~T~`), espacios de nombres (`namespace`) y relaciones UML correctas.
- **Diagramas de Relación de Entidades (`erDiagram`)**: Modelado de bases de datos relacionales con claves primarias/foráneas, tipos de datos y cardinalidades exactas.
- **Y muchos otros**: Diagramas de estado, Gantt, GitGraph, mapas mentales (`mindmap`), etc.

## Errores Comunes que esta Skill Previene

1. **El fallo de la palabra `end`**: En diagramas de flujo, la palabra `end` en minúscula rompe el motor. Esta skill enseña a la IA a escribirla siempre en mayúsculas (`End` o `END`) o a encerrarla en comillas/paréntesis.
2. **El fallo de inicio con `o` o `x`**: Conectar un nodo cuyo nombre empiece con `o` o `x` usando guiones simples (ej. `A---oB`) genera aristas especiales inválidas. La skill fuerza a usar espacios o mayúsculas.
3. **Escapes de caracteres especiales**: Enseña a codificar de forma segura elementos como el punto y coma (`#59;`) en textos de diagramas de secuencia para evitar errores de renderizado.

## Cómo Usar con tu Agente

Una vez activa la skill en tu configuración, simplemente puedes pedirle cosas como:
- *"Genera un diagrama de flujo del proceso de inicio de sesión utilizando las nuevas formas circulares y rectangulares de Mermaid."*
- *"Crea un diagrama de secuencia detallado de una llamada a una API REST con manejo de excepciones (break)."*
- *"Diseña un diagrama de clases para una aplicación de tienda en línea utilizando genéricos y relaciones de herencia y composición."*
