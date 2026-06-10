---
name: mermaidDiagramGen
description: >
  Generates highly accurate, syntactically correct, and visually beautiful Mermaid.js diagrams
  (flowcharts, sequence, class, state, entity-relationship, Gantt, pie charts, git graphs, etc.)
  leveraging the exact specifications in the Mermaid manual directory.
---

# Mermaid Diagram Generator (mermaidDiagramGen)

## Overview
The `mermaidDiagramGen` skill empowers the AI agent to draft, structure, and refine complex diagrams using the Mermaid.js language. It strictly adheres to syntax requirements, advanced layout options, and styling rules, ensuring diagrams render flawlessly in any supporting environment (e.g., Markdown viewers, GitLab, GitHub, or Mermaid Live Editor).

## Dependencies
- Access to the local manuals directory: `g:\My Drive\AI Local\Skills\Mermaid/` (contains files like `flowchart.md`, `sequenceDiagram.md`, `classDiagram.md`, `entityRelationshipDiagram.md`, etc.).

## Quick Start
To generate a basic sequence diagram with activations and autonomic numbering, use the following syntax:

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant System as System API
    database DB as User Database

    User->>+System: Request profile data
    System->>+DB: Query user records
    DB-->>-System: Return record JSON
    System-->>-User: Return visual profile
```

---

## Workflow

### 1. Diagram Selection Guide
Choose the most appropriate diagram type based on the information structure:
- **Flowcharts (`flowchart`)**: For processes, workflows, decision trees, or system architectures with conditional paths.
- **Sequence Diagrams (`sequenceDiagram`)**: For step-by-step interactions between multiple components, services, or actors over time.
- **Class Diagrams (`classDiagram`)**: For object-oriented model structures, attributes, methods, inheritance, and cardinality.
- **Entity Relationship Diagrams (`erDiagram`)**: For database schemas, tables, fields, types, and primary/foreign keys.
- **State Diagrams (`stateDiagram-v2`)**: For finite state machines, transitions, and lifecycle events of a single object or transaction.
- **Gantt Charts (`gantt`)**: For project schedules, timelines, dependencies, and resource allocations.
- **Pie Charts (`pie`)**: For simple part-to-whole comparisons or percentage distributions.
- **Git Graphs (`gitGraph`)**: For visualizing git branching models, commits, checkouts, and merges.
- **Mindmaps (`mindmap`)**: For brainstorming, radial concept mapping, and hierarchical notes.
- **User Journey (`userJourney`)**: For mapping user experience steps, actions, and satisfaction ratings.

### 2. Crucial Syntax Rules & Error Prevention

#### A. Flowcharts (Syntax manual: `flowchart.md`)
- [!WARNING] **The `end` Keyword Pitfall**: Using the word "end" in a flowchart node in lowercase will break the parser. Capitalize it (e.g., `End` or `END`), wrap it in quotes (`"end"`), or use brackets (`(end)`, `[end]`).
- [!WARNING] **First-Letter `o` or `x` Pitfall**: If a node label starts with `o` or `x` and connects via dashes (e.g., `A---oB` or `A---xB`), it will be parsed as a circle/cross edge and fail. Always add a space or capitalize it (`dev--- ops`, `dev---Ops`).
- **New Shape Definition (v11.3.0+)**: Utilize the advanced shape syntax `A@{ shape: ShapeName, label: "Label Text" }`. Key shapes include:
  - `rect` (Process), `rounded` (Event), `stadium` (Terminal), `cyl` (Database), `diamond` (Decision), `hex` (Prepare).
  - `doc` (Document), `docs` (Multiple docs), `das` (Direct access storage), `hourglass` (Collate), `bolt` (Lightning communication).
- **Edge IDs and Animations**: You can attach an ID to an edge using `ID@` and trigger animations:
  ```mermaid
  flowchart LR
      A e1@==> B
      e1@{ animate: true }
  ```

#### B. Sequence Diagrams (Syntax manual: `sequenceDiagram.md`)
- **Participant Types (Stereotypes)**: Explicitly configure database, queues, or boundaries:
  ```mermaid
  sequenceDiagram
      participant API@{ "type": "boundary", "alias": "Public API" }
      actor DB@{ "type": "database", "alias": "User DB" }
  ```
- **Half-Arrows (v11.12.3+)**: Use precise arrow types for complex operations:
  - Solid/dotted top half arrowhead: `-\|\` / `--\|\`
  - Solid/dotted bottom half arrowhead: `-\|/` / `--\|/`
- **Central Connections**: Use `()` to indicate lifelines linking to a central broker or bus:
  `Alice->>()John: Message` or `John()->>()Alice: Reply`.
- **Character Escaping**: Semicolons inside message text MUST be escaped as `#59;` to prevent breaking the parser.

#### C. Class Diagrams (Syntax manual: `classDiagram.md`)
- **Class Visibility**:
  - `+` Public, `-` Private, `#` Protected, `~` Internal/Package.
  - Classifiers at the end of fields or methods: `$` for static, `*` for abstract.
- **Generics**: Enclose generic types in tildes (`~`), e.g., `List~int~`, `Square~Shape~`.
- **Namespaces**: Group related classes:
  ```mermaid
  classDiagram
      namespace BillingService {
          class Invoice
          class Payment
      }
  ```

#### D. Entity Relationship Diagrams (Syntax manual: `entityRelationshipDiagram.md`)
- **Cardinality Notation**:
  - `|o` Zero or one, `||` Exactly one, `}o` Zero or many, `}|` One or many.
- **Field Definition**:
  ```mermaid
  erDiagram
      USER {
          int id PK
          string username "unique"
          string email
      }
  ```

---

## Common Mistakes to Avoid
1. **Lowercase `end` in Nodes**: Always capitalize or wrap in braces in flowcharts.
2. **Missing Quotes for Special Characters**: If a node or message text contains symbols, colons, or parentheses, enclose the entire label in double quotes (`"`).
3. **Invalid Relationship Symbols in Class Diagrams**: Avoid using regular arrows (`-->`) when a specific UML arrow is needed (e.g., `<|--` for Inheritance, `*--` for Composition).
