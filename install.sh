#!/bin/bash
# claude-sops installer
# Installs hooks, scripts, and slash commands for Claude Code

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           claude-sops installer                           ║"
echo "║   Standard Operating Procedures for Claude Code           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Create directories
echo "📁 Creating directories..."
mkdir -p "$CLAUDE_DIR/bin"
mkdir -p "$CLAUDE_DIR/hooks"
mkdir -p "$CLAUDE_DIR/commands"
mkdir -p "$CLAUDE_DIR/lib"
mkdir -p "$CLAUDE_DIR/shell-failures"

# Copy scripts
echo "📋 Installing scripts..."
cp "$SCRIPT_DIR/.claude/bin/claude-failures" "$CLAUDE_DIR/bin/"
cp "$SCRIPT_DIR/.claude/bin/claude-history" "$CLAUDE_DIR/bin/"
chmod +x "$CLAUDE_DIR/bin/claude-failures"
chmod +x "$CLAUDE_DIR/bin/claude-history"
echo "   ✓ claude-failures"
echo "   ✓ claude-history"

# Copy library
echo "📚 Installing SOP library..."
cp "$SCRIPT_DIR/.claude/lib/sops.py" "$CLAUDE_DIR/lib/"
echo "   ✓ sops.py"

# Copy SOP data (only if not already present - don't overwrite user customizations)
if [ ! -f "$CLAUDE_DIR/shell-failures/sops.json" ]; then
    echo "📦 Installing SOP definitions..."
    cp "$SCRIPT_DIR/.claude/shell-failures/sops.json" "$CLAUDE_DIR/shell-failures/"
    echo "   ✓ sops.json"
else
    echo "📦 SOP definitions already exist (skipping to preserve customizations)"
fi

# Copy hooks
echo "🪝 Installing hooks..."
cp "$SCRIPT_DIR/.claude/hooks/on-bash-failure.py" "$CLAUDE_DIR/hooks/"
chmod +x "$CLAUDE_DIR/hooks/on-bash-failure.py"
echo "   ✓ on-bash-failure.py"

# Copy slash commands
echo "⚡ Installing slash commands..."
cp "$SCRIPT_DIR/.claude/commands/failures.md" "$CLAUDE_DIR/commands/"
cp "$SCRIPT_DIR/.claude/commands/history.md" "$CLAUDE_DIR/commands/"
echo "   ✓ /failures"
echo "   ✓ /history"

# Update settings.json
echo "⚙️  Configuring hooks in settings.json..."

SETTINGS_FILE="$CLAUDE_DIR/settings.json"

# Define the hook configuration we need
HOOK_CONFIG='{
  "matcher": "Bash",
  "hooks": [
    {
      "type": "command",
      "command": "python3 ~/.claude/hooks/on-bash-failure.py",
      "timeout": 10
    }
  ]
}'

if [ -f "$SETTINGS_FILE" ]; then
    # Check if jq is available
    if command -v jq &> /dev/null; then
        # Check if PostToolUse hooks already exist
        if jq -e '.hooks.PostToolUse' "$SETTINGS_FILE" > /dev/null 2>&1; then
            # Check if our hook is already there
            if jq -e '.hooks.PostToolUse[] | select(.matcher == "Bash")' "$SETTINGS_FILE" > /dev/null 2>&1; then
                echo "   ✓ Hook already configured"
            else
                # Add our hook to existing PostToolUse array
                TEMP_FILE=$(mktemp)
                jq --argjson hook "$HOOK_CONFIG" '.hooks.PostToolUse += [$hook]' "$SETTINGS_FILE" > "$TEMP_FILE"
                mv "$TEMP_FILE" "$SETTINGS_FILE"
                echo "   ✓ Added hook to existing configuration"
            fi
        else
            # Create PostToolUse section
            TEMP_FILE=$(mktemp)
            jq --argjson hook "$HOOK_CONFIG" '.hooks.PostToolUse = [$hook]' "$SETTINGS_FILE" > "$TEMP_FILE"
            mv "$TEMP_FILE" "$SETTINGS_FILE"
            echo "   ✓ Created hooks configuration"
        fi
    else
        echo "   ⚠️  jq not installed - please add hook config manually"
        echo "   See README.md for the configuration to add"
    fi
else
    # Create new settings file
    cat > "$SETTINGS_FILE" << 'EOF'
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/on-bash-failure.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
EOF
    echo "   ✓ Created settings.json with hook configuration"
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                    Installation Complete!                  ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "🔄 IMPORTANT: Restart Claude Code for hooks to take effect"
echo ""
echo "📖 Available commands:"
echo "   /failures     - View failure patterns with resolutions"
echo "   /failures --sop  - Include Standard Operating Procedures"
echo "   /history      - View command history"
echo "   /history --failures  - View failed commands"
echo ""
echo "🧪 Test the hook by running a command that will fail:"
echo '   RESULT=$(echo "test"); echo $RESULT'
echo ""
echo "Happy coding! 🚀"
