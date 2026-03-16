Analyze bash command failures from this session and show what worked.

Usage:
- `/failures` - Show recent failures with resolutions
- `/failures --sop` - Include Standard Operating Procedures for each error type
- `/failures --all` - List all available SOPs
- `/failures --recent 20` - Show more failure groups

Run: `python3 ~/.claude/bin/claude-failures "$PWD" $ARGUMENTS`

After showing the output:
1. Review the PATTERNS LEARNED section
2. If you see a pattern you've hit before, apply the SOP immediately
3. When you encounter a similar error in the future, use the "WORKED" command pattern instead of the "FAILED" pattern

SOPs are loaded from:
- Global: `~/.claude/shell-failures/sops.json`
- Project: `.claude/sops.json` (overrides global)
