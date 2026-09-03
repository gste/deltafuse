# Changelog

All notable changes to the DeltaFuse framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Unified ingestion directory `docs/inbox/` (and `docs/archive/inbox/`) as the single entry point for all raw external inputs (PRDs, Confluence exports, review comments, error logs, and stacktraces).
- Dedicated `/report-bug` skill and `07-report-bug.md` job prompt for interactive bug/review triage without touching code.
- Native skill registration for Google Antigravity / Gemini CLI (`.gemini/skills/`).
- Chronological 8-step lifecycle diagram in README and documentation.

### Changed
- Replaced fragmented `docs/init/` and `docs/todo/inbox/` with a unified `docs/inbox/` following the Inbox Zero principle.
- Refocused `/fix-bug` (`08-fix-bug.md`) strictly on executing already triaged bug task files from `docs/todo/<story>/bug/`.
- Streamlined ADR template to binary `accepted: false/true` status with inlined pros & cons.
- Replaced EPIC concept with STORY across all framework templates and guidelines.

## [1.0.0] - 2026-09-03

### Added
- Initial extracted DeltaFuse Specification-Driven AI Engineering Framework.
- Core process methodology (`workflow.md`, `roles.md`, `agent-prompt.md`, `AGENTS.md`).
- Initial skill and prompt suite (`/init-requirements`, `/init-to-spec`, `/audit-spec`, `/spec-to-story`, `/plan-spec-patch`, `/implement-task`, `/fix-bug`).
- Multi-agent adapters for Cursor, Antigravity, Claude Code, GitHub Copilot, IntelliJ IDEA.
- Initialization scripts `init.sh` and `init.ps1`.