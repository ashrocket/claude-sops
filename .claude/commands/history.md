Show bash command history from this Claude Code session.

Usage:
- `/history` - Show last 20 commands
- `/history 50` - Show last 50 commands
- `/history --failures` - Show failed commands with their errors

Run: `~/.claude/bin/claude-history "$PWD" $ARGUMENTS`

If $ARGUMENTS is empty, default to 20 commands. Display the output to the user.

When showing failures, analyze the patterns and suggest how to avoid similar errors in the future.
