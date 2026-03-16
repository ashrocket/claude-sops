# claude-sops Review Coordination

## Scope
Full review of the claude-sops repo: Standard Operating Procedures for Claude Code shell failures.
9 files. Python + shell.

## Agent Assignments
- **code-reviewer**: Owns "Review Findings" section. Code quality, bugs, correctness.
- **code-simplifier**: Owns "Simplification Findings" section. Dead code, duplication with recall-skill.
- **code-architect**: Owns "Architecture Assessment" section. Relationship to recall-skill, hookify overlap, archive decision.

## Key Questions
1. Is claude-sops fully absorbed into recall-skill's /failures? Or does it have unique functionality?
2. Does hookify (hook-based prevention) make the SOP recovery pattern obsolete?
3. Should this repo be archived with a deprecation notice?
4. Is there any code here worth extracting before archiving?

## File Ownership: ALL agents are READ-ONLY for this review. No edits.

---

## Review Findings (code-reviewer)
_pending_

## Simplification Findings (code-simplifier)

### Verdict: claude-sops is fully superseded by recall-skill. Recommend archive.

Every piece of functionality in claude-sops exists in recall-skill in an equal or improved form. There is no unique code worth extracting. Below is the detailed evidence.

---

### 1. File-by-File Duplication with recall-skill

**`.claude/hooks/on-bash-failure.py` (claude-sops) vs `hooks/on-bash-failure.py` (recall-skill)**
- claude-sops hardcodes a 7-entry `ERROR_SOPS` dict directly in the hook script. recall-skill imports from `lib/sops.py` which loads SOPs from external JSON (`sops/base.json`), supporting layered global + per-project overrides.
- claude-sops only handles Job 1 (show SOP on failure). recall-skill handles both Job 1 AND Job 2 (detect resolution after success, propose saving as new SOP via state file `.last-failure`).
- claude-sops's `categorize_error()` is a hardcoded if/elif chain. recall-skill's `match_error()` uses data-driven pattern matching from JSON, which is extensible without code changes.
- The `categorize_error()` functions differ slightly between the two repos: claude-sops maps "unexpected" to `SYNTAX_ERROR`, while recall-skill maps it to `SYNTAX_ERROR` as well but through a different code path. Both also differ from the claude-sops `claude-failures` script which maps "unexpected" to `UNEXPECTED_TOKEN` -- an inconsistency within claude-sops itself.
- recall-skill adds `None` handling for `stderr`/`stdout`/`command` (e.g., `or ""` guards), which claude-sops lacks.

**`.claude/bin/claude-failures` (claude-sops) vs `bin/claude-failures` (recall-skill)**
- Both contain the same core functions: `get_session_dir()`, `get_latest_session()`, `extract_command_sequence()`/`extract_commands()`, `group_failure_sequences()`/`group_failures()`, `truncate()`, and `main()`.
- The logic is structurally identical: parse JSONL, correlate tool_use entries with tool_result entries by ID, group consecutive failures, find resolutions.
- claude-sops hardcodes another copy of `ERROR_SOPS` (8 entries including `UNEXPECTED_TOKEN` and `OTHER`, with more verbose fields like `common_causes`). recall-skill imports from `lib/sops.py` and uses `match_error()` -- no duplication.
- claude-sops has a standalone `categorize_error()` function duplicated from the hook (with a different check: requires `"(" in error_lower` for `SHELL_PARSE_ERROR`). recall-skill delegates to the shared `match_error()`.
- claude-sops has `print_sop()` inlined. recall-skill uses `format_sop()` from the shared library.

**`.claude/bin/claude-history` (claude-sops) vs `bin/claude-history` (recall-skill)**
- These two files are **byte-for-byte identical**. Exact same bash script, same inline Python block, same jq pipeline. Zero differences.

**`.claude/commands/failures.md` (claude-sops) vs `commands/failures.md` (recall-skill)**
- Nearly identical. recall-skill adds `--all` flag documentation and a note about SOP file locations. claude-sops version is a strict subset.

**`.claude/commands/history.md` (claude-sops) vs `commands/history.md` (recall-skill)**
- Identical content. One says "bash command history", the other says "shell command history" -- cosmetic only.

**`install.sh` (claude-sops) vs `install.sh` (recall-skill)**
- claude-sops has a simple single-purpose installer. recall-skill has a modular installer with `--all`, `--recall`, `--failures`, `--history`, `--minimal` flags. recall-skill's installer is a strict superset: it installs the same hook, same scripts, same commands, plus the shared library, base SOPs JSON, and recall/session features.

---

### 2. Dead Code and Unused Functions

**`ERROR_SOPS` dict in `claude-failures` (claude-sops):** The `UNEXPECTED_TOKEN` category is defined with patterns and guidance but is never matched by the hook (which maps "unexpected" to `SYNTAX_ERROR` instead). This is a dead SOP category that would never appear in hook output, only in the `claude-failures` analysis -- creating inconsistent categorization between the two scripts.

**`common_causes` field in `claude-failures` ERROR_SOPS:** Each SOP entry in `claude-failures` has a `common_causes` list. The `print_sop()` function prints these, but they are only displayed when `--sop` is passed. The hook script does not use `common_causes` at all. recall-skill consolidated this into the JSON `causes` field loaded from `sops/base.json`.

**`error_indicators` list in hook script:** The hook builds a combined output string and checks for indicators like "error", "failed", "cannot", etc. The indicator `"cannot"` will false-positive on legitimate warnings. More importantly, this filtering logic was dropped in recall-skill's version, which uses the simpler `exit_code != 0 and stderr` check -- a deliberate simplification.

**`"decision": "allow"` in hook output:** claude-sops includes `"decision": "allow"` in its hook output JSON. recall-skill's version omits it (except in the implementation plan doc). This field is unnecessary for PostToolUse hooks -- it is only meaningful for PreToolUse hooks that can block execution.

---

### 3. Inconsistencies Within claude-sops

**Two different `categorize_error()` implementations:**
- In `on-bash-failure.py`: `"parse error" in error_lower` (no parenthesis check)
- In `claude-failures`: `"parse error" in error_lower and "(" in error_lower` (requires parenthesis)
- Same error could be categorized differently depending on which script processes it.

**Two different `ERROR_SOPS` dictionaries:**
- Hook version: 7 categories, compact (no `common_causes`, shorter `sop` lists, has `example_fix` string)
- `claude-failures` version: 8 categories (adds `UNEXPECTED_TOKEN`), verbose (has `common_causes` list, `example_bad`/`example_good` strings)
- These are supposed to represent the same knowledge base but have diverged.

**`truncate()` function:**
- Hook: no null check, default length 120 for command display
- `claude-failures`: has null check returning `"(none)"`, default length 150
- Different truncation lengths mean the same command could display differently.

---

### 4. Hookify / Prevention-Based Hooks

There is no `hookify` project in the workspace -- it is only referenced in ReviewCoord.md's questions. However, the question is conceptually valid: does a PreToolUse prevention hook make PostToolUse SOP recovery obsolete?

The answer is nuanced. A PreToolUse hook could theoretically intercept and reject/rewrite known-bad patterns before execution (e.g., block `$()` command substitution). But:
- The SOP pattern still has value for **unknown/novel errors** that cannot be predicted
- recall-skill already handles both the reactive (PostToolUse) and learning (save-as-SOP) patterns
- If hookify were built, it would complement recall-skill, not replace it -- and it would certainly not need claude-sops as a dependency since recall-skill already has the complete SOP infrastructure

---

### 5. Summary

| Aspect | claude-sops | recall-skill | Winner |
|--------|-------------|--------------|--------|
| Hook script | Hardcoded SOPs, no state tracking | External JSON SOPs, state tracking, resolution detection | recall-skill |
| Failures command | Hardcoded SOPs, duplicate categorizer | Shared library, data-driven matching | recall-skill |
| History command | Identical | Identical | Tie (same file) |
| SOP storage | Hardcoded in Python | External JSON, layered (global + project) | recall-skill |
| Error categories | 7-8 hardcoded | 10 in base.json, extensible without code changes | recall-skill |
| Install script | Simple, single-purpose | Modular with selective install | recall-skill |
| Internal consistency | Two divergent SOP dicts, two different categorizers | Single shared library | recall-skill |

**Recommendation:** Archive claude-sops with a deprecation notice pointing to recall-skill. There is nothing to extract -- recall-skill absorbed all functionality and improved upon it. The consolidation doc at `recall-skill/docs/plans/2025-01-26-consolidation.md` explicitly documents this absorption.

## Architecture Assessment (code-architect)
_pending_
