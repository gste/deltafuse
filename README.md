# DeltaFuse ⚡

[ **English** ](README.md) | [ Русский ](README.ru.md)

> **Specification-Driven AI Engineering Framework**
> A deterministic, agent-agnostic methodology for human-in-the-loop software development with autonomous AI agents.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Compatibility](https://img.shields.io/badge/Agents-Cursor%20%7C%20Antigravity%20%7C%20Claude%20%7C%20Copilot%20%7C%20IDEA-success.svg)]()

---

## 🗺️ How DeltaFuse Works (End-to-End Lifecycle)

```mermaid
flowchart TD
    classDef human fill:#fff3cd,stroke:#856404,stroke-width:2px,color:#856404;
    classDef skill fill:#e8f4fd,stroke:#1d70b8,stroke-width:2px,color:#0c5460;
    classDef law fill:#d4edda,stroke:#155724,stroke-width:2px,color:#155724;
    classDef inbox fill:#f8f9fa,stroke:#6c757d,stroke-width:2px,color:#383d41;

    Raw["💡 Idea / PRD / Confluence / Error Log / Review"] --> Inbox["📥 docs/inbox/<br><b>UNIFIED ENTRY POINT</b>"]:::inbox

    Inbox --> S1["/triage<br><b>01. Universal Triage</b><br><i>Analysis, Stop-and-Ask, Spec evaluation</i>"]:::skill

    S1 -->|"Bootstrap / New spec"| SpecDraft["📄 docs/spec/ & docs/decisions/ (Draft)"]
    S1 -->|"Architectural fork"| ADRDraft["🏛️ docs/decisions/NNNN-*.md (Draft)"]
    S1 -->|"Ready task / Bug"| TaskInbox["📋 docs/todo/&lt;story&gt;/NN-*.md<br><b>Task Queue</b>"]:::inbox

    SpecDraft --> S2["/audit-spec<br><b>02. Auditor</b>"]:::skill
    ADRDraft --> S2

    S2 <-->|"Iterative ADR review"| Gate1{{"👤 Human Gate<br>Decide ADR (`accepted: true`)"}}:::human

    Gate1 -->|"All ADRs accepted (`true`) & mirrored"| SpecLaw["⚖️ docs/spec/<br><b>SOLE IMPLEMENTATION LAW</b>"]:::law

    SpecLaw -->|"Plan Story / Slicing from git diff"| S3["/plan-story<br><b>03. Planner</b>"]:::skill
    S3 --> TaskInbox

    TaskInbox --> S4["/implement-task<br><b>04. Implementer (TDD)</b><br><i>Failing test (Red) ➔ Code (Green)</i>"]:::skill

    S4 --> Code["🧪 Code + Automated Tests (Green)"]
    Code --> Gate2{{"👤 Human Gate<br>PR Review & git push"}}:::human
```

---

## 🎯 What is DeltaFuse?

**DeltaFuse** is an operational framework for AI-native software engineering that establishes:

- **Specification (`docs/spec/`)** as the sole implementation law.
- **Unified Ingestion (`docs/inbox/`)** as the single entry point for all raw external inputs (PRDs, exports, error dumps, review notes) triaged via Inbox Zero into `docs/archive/inbox/`.
- **4 orthogonal skills** covering the entire lifecycle from idea to verified code.
- **Strict Human Gates** retaining absolute authority over architectural decisions, PR approvals, and `git push`.

---

## 🔄 DeltaFuse Skill Suite

| # | Command / Skill | Role | Primary Artifact | When to Run |
|---|---|---|---|---|
| **01** | [`/triage`](docs/process/prompts/01-triage.md) | Auditor / Triage | Spec / ADR / `docs/todo/<story>/NN-*.md` | Any raw input: new PRD, idea, review comment, or error log from `docs/inbox/` or chat. |
| **02** | [`/audit-spec`](docs/process/prompts/02-audit-spec.md) | Auditor | Report, ADRs, `docs/spec/**` | Validate consistency, mirror accepted ADRs, identify hidden forks. |
| **03** | [`/plan-story`](docs/process/prompts/03-plan-story.md) | Planner | `docs/todo/<story>/NN-*.md` | Slice accepted specification modules or spec `git diff` into atomic task files. |
| **04** | [`/implement-task`](docs/process/prompts/04-implement-task.md) | Implementer | Code, Tests, PR | Universal TDD implementation of any task file in `docs/todo/<story>/NN-*.md`. |

---

## 📁 Repository Directory Layout

```text
├── .cursorrules              # Cursor IDE instructions
├── AGENTS.md                 # Autonomous Agent & AI CLI instructions
├── CLAUDE.md                 # Claude Code CLI instructions
├── CHANGELOG.md              # Project changelog
├── docs/
│   ├── process/              # DeltaFuse methodology, roles, workflows
│   │   └── prompts/          # Procedural job prompts (01..04)
│   ├── inbox/                # UNIFIED INBOX for all incoming raw files (PRD, logs, dumps, reviews)
│   ├── decisions/            # Architecture Decision Records (ADRs)
│   ├── spec/                 # Modular specification (IMPLEMENTATION LAW)
│   │   ├── README.md         # Single acceptance entry (TOC, Tour, Coverage)
│   │   └── 00-context.md     # In/out of scope, actors, human-gated areas
│   ├── todo/                 # Atomic task queues
│   │   └── <story>/          # Story task files (NN-<slug>.md)
│   └── archive/              # Processed historical artifacts
│       └── inbox/
├── .cursor/skills/           # Cursor skills
├── .gemini/skills/           # Google Antigravity / Gemini CLI skills
└── .agents/skills/           # Universal Agent skills
```