"""PreToolUse hook: always ask the user before any git or gh command runs.

Reads the tool call JSON from stdin. If the shell command contains a git or gh
invocation anywhere (including after &&, ;, |), it returns an "ask" decision so
Claude Code shows a permission prompt, even in auto or accept modes.
"""
import json
import re
import sys

# Matches git / gh / git.exe / gh.exe as a command word, e.g. "git push",
# "cd repo && gh pr create", "& git.exe status".
GIT_PATTERN = re.compile(r"(^|[\s;&|(`'\"])(git|gh)(\.exe)?(\s|$)", re.IGNORECASE)


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return

    command = payload.get("tool_input", {}).get("command", "")
    if not GIT_PATTERN.search(command):
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": "Git/GitHub command detected. User approval is required before it runs.",
        }
    }))


if __name__ == "__main__":
    main()
