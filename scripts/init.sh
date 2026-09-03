#!/usr/bin/env bash
# DeltaFuse Project Initializer
set -euo pipefail

TARGET_DIR="${1:-.}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Initializing DeltaFuse in $TARGET_DIR..."

mkdir -p "$TARGET_DIR/docs/process"
mkdir -p "$TARGET_DIR/docs/init"
mkdir -p "$TARGET_DIR/docs/decisions"
mkdir -p "$TARGET_DIR/docs/spec"
mkdir -p "$TARGET_DIR/docs/todo"
mkdir -p "$TARGET_DIR/docs/todo/inbox"
mkdir -p "$TARGET_DIR/docs/archive/init"
mkdir -p "$TARGET_DIR/docs/archive/inbox"
mkdir -p "$TARGET_DIR/.cursor/skills"
mkdir -p "$TARGET_DIR/.agents/skills"
mkdir -p "$TARGET_DIR/.gemini/skills"

# Copy core
cp "$SCRIPT_DIR/AGENTS.md" "$TARGET_DIR/AGENTS.md"
cp "$SCRIPT_DIR/CLAUDE.md" "$TARGET_DIR/CLAUDE.md"
cp -r "$SCRIPT_DIR/docs/process/"* "$TARGET_DIR/docs/process/"

# Copy skills
cp -r "$SCRIPT_DIR/skills/"* "$TARGET_DIR/.cursor/skills/"
cp -r "$SCRIPT_DIR/skills/"* "$TARGET_DIR/.agents/skills/"
cp -r "$SCRIPT_DIR/skills/"* "$TARGET_DIR/.gemini/skills/"

# Copy templates if targets don't exist
[ -f "$TARGET_DIR/docs/todo/README.md" ] || cp "$SCRIPT_DIR/templates/docs/todo/README.md" "$TARGET_DIR/docs/todo/README.md"
[ -f "$TARGET_DIR/docs/decisions/README.md" ] || cp "$SCRIPT_DIR/templates/docs/decisions/README.md" "$TARGET_DIR/docs/decisions/README.md"
[ -f "$TARGET_DIR/docs/decisions/0000-template.md" ] || cp "$SCRIPT_DIR/templates/docs/decisions/0000-template.md" "$TARGET_DIR/docs/decisions/0000-template.md"
[ -f "$TARGET_DIR/CHANGELOG.md" ] || cp "$SCRIPT_DIR/templates/CHANGELOG.md" "$TARGET_DIR/CHANGELOG.md"

echo "DeltaFuse initialized successfully!"