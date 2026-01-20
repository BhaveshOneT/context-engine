#!/usr/bin/env python3
"""
Context Engine: Claude Code Hooks Setup
Generates the hooks configuration for Claude Code settings.
"""

import os
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
MEMORY_DIR = SCRIPT_DIR.parent

# Colors
GREEN = '\033[0;32m'
YELLOW = '\033[0;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'


def get_claude_settings_path() -> Path:
    """Get Claude Code settings path"""
    # Check for project-level settings first
    project_settings = MEMORY_DIR.parent / '.claude' / 'settings.json'
    if project_settings.parent.exists():
        return project_settings

    # Fall back to user settings
    home = Path.home()
    return home / '.claude' / 'settings.json'


def generate_hooks_config() -> dict:
    """Generate the hooks configuration"""
    ce_root = str(MEMORY_DIR)

    return {
        "hooks": {
            "UserPromptSubmit": [
                {
                    "matcher": "",
                    "hooks": [
                        f"python3 {ce_root}/scripts/prompt_tracker.py record \"$PROMPT\""
                    ]
                }
            ],
            "PostToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        f"python3 {ce_root}/scripts/hooks_PostToolUse_ErrorCapture.py"
                    ]
                }
            ],
            "SessionStart": [
                {
                    "matcher": "",
                    "hooks": [
                        f"bash {ce_root}/scripts/hooks_SessionStart.sh"
                    ]
                }
            ],
            "SessionEnd": [
                {
                    "matcher": "",
                    "hooks": [
                        f"bash {ce_root}/scripts/hooks_SessionEnd.sh"
                    ]
                }
            ]
        }
    }


def print_manual_setup():
    """Print manual setup instructions"""
    ce_root = str(MEMORY_DIR)

    print(f"""
{BLUE}{'━' * 60}{NC}
{GREEN}Claude Code Hooks Configuration{NC}
{BLUE}{'━' * 60}{NC}

Add this to your Claude Code settings (~/.claude/settings.json):

{YELLOW}{{
  "hooks": {{
    "UserPromptSubmit": [
      {{
        "matcher": "",
        "hooks": ["python3 {ce_root}/scripts/prompt_tracker.py record \\"$PROMPT\\""]
      }}
    ],
    "PostToolUse": [
      {{
        "matcher": "Bash",
        "hooks": ["python3 {ce_root}/scripts/hooks_PostToolUse_ErrorCapture.py"]
      }}
    ]
  }}
}}{NC}

{BLUE}{'━' * 60}{NC}
{GREEN}What each hook does:{NC}

• UserPromptSubmit  → Tracks your prompts automatically
• PostToolUse:Bash  → Captures errors from failed commands

These hooks make the Context Engine 100% automatic!
{BLUE}{'━' * 60}{NC}
""")


def setup_hooks():
    """Setup hooks in Claude Code settings"""
    settings_path = get_claude_settings_path()

    # Read existing settings
    settings = {}
    if settings_path.exists():
        try:
            with open(settings_path, 'r') as f:
                settings = json.load(f)
        except json.JSONDecodeError:
            settings = {}

    # Merge hooks
    hooks_config = generate_hooks_config()

    if 'hooks' not in settings:
        settings['hooks'] = {}

    for hook_name, hook_list in hooks_config['hooks'].items():
        if hook_name not in settings['hooks']:
            settings['hooks'][hook_name] = hook_list
        # If hooks exist, we don't override - user may have custom config

    # Ensure directory exists
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    # Write settings
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)

    print(f"{GREEN}✓{NC} Hooks configured in {settings_path}")
    return True


def main():
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--show':
        print_manual_setup()
    else:
        print(f"\n{BLUE}Setting up Claude Code hooks...{NC}\n")
        try:
            setup_hooks()
            print(f"\n{GREEN}Hooks are now active!{NC}")
            print(f"  • Prompts will be tracked automatically")
            print(f"  • Errors will be captured automatically")
            print(f"\nRun '{YELLOW}./ce activate{NC}' to start using Context Engine\n")
        except Exception as e:
            print(f"{YELLOW}Could not auto-configure hooks: {e}{NC}")
            print(f"Please configure manually:\n")
            print_manual_setup()


if __name__ == '__main__':
    main()
