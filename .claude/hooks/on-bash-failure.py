#!/usr/bin/env python3
"""
PostToolUse hook that detects bash command failures and provides SOP guidance.
Automatically triggers after any Bash command to help Claude learn from errors.
"""

import json
import sys

# Standard Operating Procedures for each error type
ERROR_SOPS = {
    "SHELL_PARSE_ERROR": {
        "description": "zsh cannot parse command substitution or special characters",
        "sop": [
            "AVOID $(...) - use simple pipes instead",
            "Split complex commands into multiple simple commands",
            "Use the Read tool instead of cat/head for file contents",
            "Run simple command first, then use result in next command"
        ],
        "example_fix": "Instead of VAR=$(cmd); use $VAR → run: cmd | next_cmd OR run cmd first, use Read tool"
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

def categorize_error(error_msg):
    """Categorize the error type."""
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

def main():
    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, IOError):
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    tool_response = hook_input.get("tool_response", {})

    # Only process Bash
    if tool_name != "Bash":
        sys.exit(0)

    # Check for errors - look at exit code and stderr
    exit_code = tool_response.get("exitCode", 0)
    stderr = tool_response.get("stderr", "")
    stdout = tool_response.get("stdout", "")

    # Not an error
    if exit_code == 0 and not stderr:
        sys.exit(0)

    # Some commands legitimately return non-zero (like grep with no matches)
    # Only provide guidance for actual errors
    error_indicators = ["error", "failed", "cannot", "denied", "not found", "parse error", "syntax"]
    combined_output = (stderr + stdout).lower()

    is_real_error = exit_code != 0 and any(ind in combined_output for ind in error_indicators)

    if not is_real_error:
        sys.exit(0)

    # Get error details
    error_msg = stderr if stderr else stdout
    error_type = categorize_error(error_msg)
    sop = ERROR_SOPS.get(error_type, ERROR_SOPS["OTHER"])

    # Get the failed command (truncate if too long)
    failed_cmd = tool_input.get("command", "unknown")
    if len(failed_cmd) > 120:
        failed_cmd = failed_cmd[:120] + "..."

    # Build concise feedback
    feedback = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  BASH COMMAND FAILED: {error_type}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Command: {failed_cmd}

SOP Fix Steps:
"""
    for i, step in enumerate(sop['sop'], 1):
        feedback += f"  {i}. {step}\n"

    feedback += f"""
Example: {sop['example_fix']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 ESCALATION RULES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 1st failure → Try SOP steps above
• 2nd failure → Try alternative approaches
• 3rd failure → **ASK THE USER FOR HELP**

ASK IMMEDIATELY if:
• SOP doesn't seem applicable
• Error is unusual/unfamiliar
• You're unsure what to try

Say: "I've hit {error_type} and tried [X]. The SOP suggests [Y] but
that doesn't fit because [Z]. Can you help? Should we update the SOP?"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    # Return as context injection
    output = {
        "decision": "allow",
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": feedback
        }
    }

    print(json.dumps(output))
    sys.exit(0)

if __name__ == "__main__":
    main()
