#!/usr/bin/env python3
"""
PostToolUse hook for Bash commands.
Job 1: On failure - show matching SOP, save state for resolution tracking
Job 2: On success after failure - show what worked, propose saving as new SOP
"""

import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add lib to path
LIB_DIR = Path(__file__).resolve().parent.parent / "lib"
INSTALLED_LIB_DIR = Path.home() / ".claude" / "lib"

# Try installed location first, then source location
if INSTALLED_LIB_DIR.exists():
    sys.path.insert(0, str(INSTALLED_LIB_DIR))
elif LIB_DIR.exists():
    sys.path.insert(0, str(LIB_DIR))

try:
    from sops import load_sops, match_error, format_sop
    HAS_SOPS_LIB = True
except ImportError:
    HAS_SOPS_LIB = False

# Inline fallback SOPs (used when sops.py library not available)
FALLBACK_SOPS = {
    "SHELL_PARSE_ERROR": {
        "description": "zsh cannot parse command substitution or special characters",
        "sop": [
            "AVOID $(...) - use simple pipes instead",
            "Split complex commands into multiple simple commands",
            "Use the Read tool instead of cat/head for file contents",
            "Run simple command first, then use result in next command"
        ],
        "example_fix": "Instead of VAR=$(cmd); use $VAR -> run: cmd | next_cmd OR run cmd first, use Read tool"
    },
    "SYNTAX_ERROR": {
        "description": "Python or shell syntax error in inline code",
        "sop": [
            "Extract dict values to variables before f-string",
            "Write Python to a script file instead of using -c",
            "Avoid backslash escapes inside f-strings",
            "Use single quotes for the outer string in python3 -c"
        ],
        "example_fix": "val = d['key']; print(f'{val}') instead of print(f\"{d['key']}\")"
    },
    "COMMAND_NOT_FOUND": {
        "description": "Command/binary doesn't exist or isn't in PATH",
        "sop": [
            "Check if installed: which <command>",
            "Install if needed: brew install <package>",
            "Use alternative command (grep instead of rg, find instead of fd)"
        ],
        "example_fix": "which rg || use grep -r instead"
    },
    "PERMISSION_DENIED": {
        "description": "No permission to execute or access file",
        "sop": [
            "Make script executable: chmod +x script.sh",
            "Run with interpreter: python3 script.py instead of ./script.py",
            "Check file ownership: ls -la file"
        ],
        "example_fix": "python3 ./script.py instead of ./script.py"
    },
    "FILE_NOT_FOUND": {
        "description": "File or directory doesn't exist",
        "sop": [
            "Verify path exists: ls -la <parent_dir>",
            "Check current directory: pwd",
            "Create directory if needed: mkdir -p <dir>",
            "Use absolute paths to avoid confusion"
        ],
        "example_fix": "ls -la parent_dir first, then proceed"
    },
    "NON_ZERO_EXIT": {
        "description": "Command ran but returned non-zero exit code",
        "sop": [
            "Check stderr output for details",
            "For grep: exit 1 just means no match (often not an error)",
            "Add || true if exit code doesn't matter",
            "Check command arguments are correct"
        ],
        "example_fix": "grep pattern file || echo 'No matches' (if no-match is ok)"
    },
    "OTHER": {
        "description": "Uncategorized error",
        "sop": [
            "Read the error message carefully",
            "Try a simpler version of the command",
            "Check command documentation: man <cmd> or <cmd> --help",
            "ASK THE USER - this might need a new SOP category"
        ],
        "example_fix": "Ask user for guidance on unfamiliar errors"
    }
}

STATE_FILE = Path.home() / ".claude" / "shell-failures" / ".last-failure"
RESOLUTION_WINDOW = timedelta(minutes=5)


def read_state():
    """Read last failure state if recent enough."""
    if not STATE_FILE.exists():
        return None

    try:
        with open(STATE_FILE) as f:
            state = json.load(f)

        timestamp = datetime.fromisoformat(state["timestamp"])
        if datetime.now() - timestamp > RESOLUTION_WINDOW:
            STATE_FILE.unlink(missing_ok=True)
            return None

        return state
    except (json.JSONDecodeError, IOError, KeyError):
        return None


def write_state(error_type, failed_cmd, error_msg):
    """Save failure state for resolution detection."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    state = {
        "timestamp": datetime.now().isoformat(),
        "error_type": error_type,
        "failed_command": failed_cmd[:500],
        "error_message": error_msg[:500]
    }

    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def clear_state():
    """Clear failure state after resolution."""
    STATE_FILE.unlink(missing_ok=True)


def truncate(s, length=100):
    """Truncate string for display."""
    if not s:
        return "(none)"
    if len(s) > length:
        return s[:length] + "..."
    return s


def categorize_error(error_msg):
    """Categorize the error type from error message text."""
    error_lower = error_msg.lower()

    if "parse error" in error_lower:
        return "SHELL_PARSE_ERROR"
    if "command not found" in error_lower:
        return "COMMAND_NOT_FOUND"
    if "permission denied" in error_lower:
        return "PERMISSION_DENIED"
    if "no such file" in error_lower or "not found" in error_lower:
        return "FILE_NOT_FOUND"
    if "syntax" in error_lower:
        return "SYNTAX_ERROR"
    if "unexpected" in error_lower:
        return "SYNTAX_ERROR"
    return "OTHER"


def get_sop_text(error_msg):
    """Get SOP text using library if available, falling back to inline SOPs."""
    if HAS_SOPS_LIB:
        sops = load_sops()
        match = match_error(error_msg, sops)
        if match:
            name, sop = match
            return name, format_sop(name, sop)

    # Fallback to inline categorization
    error_type = categorize_error(error_msg)
    sop = FALLBACK_SOPS.get(error_type, FALLBACK_SOPS["OTHER"])

    lines = [f"SOP: {error_type}", f"  {sop['description']}", "", "  Fix Steps:"]
    for i, step in enumerate(sop['sop'], 1):
        lines.append(f"    {i}. {step}")
    lines.append(f"  Example: {sop['example_fix']}")

    return error_type, "\n".join(lines)


def main():
    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, IOError):
        sys.exit(0)

    try:
        tool_name = hook_input.get("tool_name", "")
        tool_input = hook_input.get("tool_input", {})
        tool_response = hook_input.get("tool_response", {})

        # Only process Bash
        if tool_name != "Bash":
            sys.exit(0)

        command = tool_input.get("command", "") or ""
        exit_code = tool_response.get("exitCode", 0) or 0
        stderr = tool_response.get("stderr", "") or ""  # Handle None
        stdout = tool_response.get("stdout", "") or ""  # Handle None

        # Check if this is a failure
        is_error = exit_code != 0 and stderr

        # Also check for error indicators in output for edge cases
        if not is_error and exit_code != 0:
            error_indicators = ["error", "failed", "cannot", "denied", "not found", "parse error", "syntax"]
            combined_output = (stderr + stdout).lower()
            is_error = any(ind in combined_output for ind in error_indicators)

        if is_error:
            # Job 1: Show SOP on failure
            error_msg = stderr if stderr else stdout
            error_type, sop_text = get_sop_text(error_msg)
            write_state(error_type, command, error_msg)

            # Get the failed command (truncate if too long)
            failed_cmd = truncate(command, 120)

            feedback = f"""
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\u26a0\ufe0f  BASH COMMAND FAILED: {error_type}
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

Command: {failed_cmd}

{sop_text}

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001f6d1 ESCALATION RULES:
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\u2022 1st failure \u2192 Try SOP steps above
\u2022 2nd failure \u2192 Try alternative approaches
\u2022 3rd failure \u2192 **ASK THE USER FOR HELP**

ASK IMMEDIATELY if:
\u2022 SOP doesn't seem applicable
\u2022 Error is unusual/unfamiliar
\u2022 You're unsure what to try
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
"""

            output = {
                "decision": "allow",
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": feedback
                }
            }
            print(json.dumps(output))

        else:
            # Job 2: Check if this resolves a previous failure
            state = read_state()

            if state:
                clear_state()

                feedback = f"""
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\u2705 That command worked after {state['error_type']}
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

Failed: {truncate(state['failed_command'])}
Worked: {truncate(command)}

Save as SOP? Reply: "save global", "save project", or continue working
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
"""

                output = {
                    "decision": "allow",
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": feedback
                    }
                }
                print(json.dumps(output))
            else:
                # No state, nothing to do
                sys.exit(0)

    except Exception:
        # Fail silently - don't crash the hook
        sys.exit(0)


if __name__ == "__main__":
    main()
