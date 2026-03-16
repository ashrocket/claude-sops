#!/bin/bash
# Restore the installed (Jan 2025) versions of claude-sops
# These versions use ~/.claude/lib/sops.py and have resolution tracking

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"

echo "Restoring installed claude-sops backup..."

mkdir -p "$CLAUDE_DIR/bin" "$CLAUDE_DIR/hooks" "$CLAUDE_DIR/lib" "$CLAUDE_DIR/commands" "$CLAUDE_DIR/shell-failures"

cp "$SCRIPT_DIR/bin/claude-failures" "$CLAUDE_DIR/bin/"
cp "$SCRIPT_DIR/bin/claude-history" "$CLAUDE_DIR/bin/"
cp "$SCRIPT_DIR/hooks/on-bash-failure.py" "$CLAUDE_DIR/hooks/"
cp "$SCRIPT_DIR/lib/sops.py" "$CLAUDE_DIR/lib/"
cp "$SCRIPT_DIR/commands/failures.md" "$CLAUDE_DIR/commands/"
cp "$SCRIPT_DIR/commands/history.md" "$CLAUDE_DIR/commands/"
cp "$SCRIPT_DIR/shell-failures/sops.json" "$CLAUDE_DIR/shell-failures/"

chmod +x "$CLAUDE_DIR/bin/claude-failures" "$CLAUDE_DIR/bin/claude-history" "$CLAUDE_DIR/hooks/on-bash-failure.py"

echo "Restored. Restart Claude Code to activate."
