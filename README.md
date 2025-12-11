# claude-sops

**Standard Operating Procedures for Claude Code** — A learning system that helps Claude Code remember what works and avoid repeating mistakes.

```
┌─────────────────────────────────────────────────────────────┐
│  Command fails → Hook detects → SOP provided → Fix applied │
│                                                             │
│  ❌ RESULT=$(ls -t); echo $RESULT                          │
│     ↓                                                       │
│  ⚠️  SHELL_PARSE_ERROR detected                            │
│     ↓                                                       │
│  📋 SOP: "Avoid $(...), use simple pipes instead"          │
│     ↓                                                       │
│  ✅ ls -t | head -1                                        │
└─────────────────────────────────────────────────────────────┘
```

## Why?

Claude Code is powerful, but it can hit the same shell errors repeatedly — especially zsh parse errors with command substitution. This toolkit:

1. **Detects failures** as they happen with a PostToolUse hook
2. **Provides immediate guidance** with categorized SOPs
3. **Tracks patterns** so you can see what worked
4. **Enforces escalation** — after 3 failures, Claude asks YOU for help

## Quick Start

```bash
# Clone the repo
git clone https://github.com/ashrocket/claude-sops.git
cd claude-sops

# Run the installer
./install.sh

# Restart Claude Code to activate hooks
```

## What's Included

```
.claude/
├── hooks/
│   └── on-bash-failure.py    # Auto-triggers on bash errors
├── bin/
│   ├── claude-failures       # Analyze failures & resolutions
│   └── claude-history        # View command history
└── commands/
    ├── failures.md           # /failures slash command
    └── history.md            # /history slash command
```

## Features

### 🔴 Automatic Failure Detection

When any bash command fails, the hook instantly categorizes the error and provides structured guidance:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  BASH COMMAND FAILED: SHELL_PARSE_ERROR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Command: RESULT=$(echo "test" | sed 's/t/x/g'); echo $RESULT

SOP Fix Steps:
  1. AVOID $(...) - use simple pipes instead
  2. Split complex commands into multiple simple commands
  3. Use the Read tool instead of cat/head for file contents
  4. Run simple command first, then use result in next command

Example: Instead of VAR=$(cmd); use $VAR → run: cmd | next_cmd
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 📊 Error Categories & SOPs

| Error Type | Description | Key Fix |
|------------|-------------|---------|
| `SHELL_PARSE_ERROR` | zsh can't parse `$(...)` | Use pipes, split commands |
| `SYNTAX_ERROR` | Python/shell syntax issues | Extract dict values first |
| `COMMAND_NOT_FOUND` | Binary not in PATH | `which cmd` or `brew install` |
| `PERMISSION_DENIED` | Can't execute/access | `chmod +x` or use interpreter |
| `FILE_NOT_FOUND` | Path doesn't exist | Verify with `ls -la` first |
| `NON_ZERO_EXIT` | Command returned error | Check stderr, use `|| true` |

### 🛑 Escalation Rules

The system enforces a clear escalation path:

| Attempt | Action |
|---------|--------|
| 1st failure | Apply SOP steps |
| 2nd failure | Try alternative approaches |
| 3rd failure | **ASK THE USER FOR HELP** |

Claude is prompted to ask immediately if:
- The SOP doesn't seem applicable
- The error is unusual/unfamiliar
- Unsure which approach to try

### 📜 Slash Commands

**`/failures`** — View failure patterns with resolutions

```bash
/failures           # Recent failures
/failures --sop     # Include full SOPs
/failures --recent 20  # More history
```

**`/history`** — View command history

```bash
/history            # Last 20 commands
/history 50         # Last 50 commands
/history --failures # Only failed commands
```

## Example: Learning in Action

Here's what learning from failure looks like:

```
============================================================
FAILURE GROUP #1 - 2 attempt(s)
Error Type: SHELL_PARSE_ERROR
============================================================

  Attempt 1 [FAILED]:
    CMD:   LATEST=$(ls -t ~/.claude/projects/*.jsonl | head -1); cat "$LATEST"
    ERROR: (eval):1: parse error near `('

  Attempt 2 [FAILED]:
    CMD:   LATEST=`ls -t ~/.claude/projects/*.jsonl | head -1`; cat "$LATEST"
    ERROR: (eval):1: parse error near `('

  RESOLUTION [WORKED]:
    CMD:   ls -t ~/.claude/projects/*.jsonl | head -1

============================================================
LEARNED PATTERNS
============================================================

SHELL_PARSE_ERROR (1 occurrences):
  DONT: LATEST=$(ls -t ~/.claude/projects/*.jsonl | head -1); cat "$LATEST"
  DO:   ls -t ~/.claude/projects/*.jsonl | head -1
```

## Installation Details

The installer will:

1. Copy scripts to `~/.claude/bin/`
2. Copy hooks to `~/.claude/hooks/`
3. Copy slash commands to `~/.claude/commands/`
4. Merge hook configuration into `~/.claude/settings.json`

### Manual Installation

If you prefer manual setup:

```bash
# Create directories
mkdir -p ~/.claude/{bin,hooks,commands}

# Copy files
cp .claude/bin/* ~/.claude/bin/
cp .claude/hooks/* ~/.claude/hooks/
cp .claude/commands/* ~/.claude/commands/

# Make executable
chmod +x ~/.claude/bin/* ~/.claude/hooks/*

# Add hook to settings.json (merge with existing)
```

Add this to your `~/.claude/settings.json`:

```json
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
```

## Adding Custom SOPs

Edit the `ERROR_SOPS` dictionary in both:
- `~/.claude/hooks/on-bash-failure.py` (for real-time guidance)
- `~/.claude/bin/claude-failures` (for history analysis)

Example new category:

```python
"NETWORK_ERROR": {
    "description": "Network request failed",
    "sop": [
        "Check internet connection",
        "Verify URL is correct",
        "Check for proxy/firewall issues",
        "Try with curl -v for debugging"
    ],
    "example_fix": "curl -v URL to debug connection issues"
}
```

## How It Works

### The Hook System

Claude Code supports [hooks](https://docs.anthropic.com/en/docs/claude-code/hooks) — scripts that run before/after tool use. This project uses a `PostToolUse` hook that:

1. Receives JSON with tool name, input, and response
2. Checks if it was a Bash command that failed
3. Categorizes the error type
4. Returns JSON with `additionalContext` that gets injected into Claude's context

### Session History

Claude Code stores session transcripts as JSONL files in `~/.claude/projects/`. The `claude-failures` script parses these to:

1. Extract all bash commands and their results
2. Group consecutive failures
3. Find what command eventually worked
4. Build a "learned patterns" summary

## Requirements

- Claude Code CLI
- Python 3.6+
- `jq` (for history command)
- macOS/Linux (zsh or bash)

## Contributing

Found a new error pattern? Add it! PRs welcome for:

- New error categories and SOPs
- Better error detection regex
- Additional slash commands
- Platform-specific fixes

## License

MIT

---

*Built with Claude Code, for Claude Code* 🤖
