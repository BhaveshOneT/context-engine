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


def get_ce_root() -> Path:
    """Determine Context Engine root path."""
    env_root = os.environ.get('PROJECT_MEMORY_DIR')
    if env_root:
        return Path(env_root).resolve()
    return MEMORY_DIR.resolve()


def generate_hooks_config(ce_root: Path) -> dict:
    """Generate the hooks configuration"""
    ce_root_str = str(ce_root)

    return {
        "hooks": {
            "UserPromptSubmit": [
                {
                    "matcher": {},
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"bash {ce_root_str}/scripts/hooks_UserPromptSubmit.sh",
                        }
                    ],
                }
            ],
            "PostToolUse": [
                {
                    "matcher": {"tools": ["Bash"]},
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"python3 {ce_root_str}/scripts/hooks_PostToolUse_ErrorCapture.py",
                        }
                    ],
                }
            ],
            "SessionStart": [
                {
                    "matcher": {},
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"bash {ce_root_str}/scripts/hooks_SessionStart.sh",
                        }
                    ],
                }
            ],
            "SessionEnd": [
                {
                    "matcher": {},
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"bash {ce_root_str}/scripts/hooks_SessionEnd.sh",
                        }
                    ],
                }
            ],
        }
    }


def print_manual_setup():
    """Print manual setup instructions"""
    ce_root = str(get_ce_root())

    print(f"""
{BLUE}{'━' * 60}{NC}
{GREEN}Claude Code Hooks Configuration{NC}
{BLUE}{'━' * 60}{NC}

Add this to your Claude Code settings (~/.claude/settings.json):

{YELLOW}{{
  "hooks": {{
    "UserPromptSubmit": [
      {{
        "matcher": {{}},
        "hooks": [{{"type": "command", "command": "bash {ce_root}/scripts/hooks_UserPromptSubmit.sh"}}]
      }}
    ],
    "PostToolUse": [
      {{
        "matcher": {{"tools": ["Bash"]}},
        "hooks": [{{"type": "command", "command": "python3 {ce_root}/scripts/hooks_PostToolUse_ErrorCapture.py"}}]
      }}
    ],
    "SessionStart": [
      {{
        "matcher": {{}},
        "hooks": [{{"type": "command", "command": "bash {ce_root}/scripts/hooks_SessionStart.sh"}}]
      }}
    ],
    "SessionEnd": [
      {{
        "matcher": {{}},
        "hooks": [{{"type": "command", "command": "bash {ce_root}/scripts/hooks_SessionEnd.sh"}}]
      }}
    ]
  }}
}}{NC}

{BLUE}{'━' * 60}{NC}
{GREEN}What each hook does:{NC}

• UserPromptSubmit  → Tracks your prompts automatically
• PostToolUse:Bash  → Captures errors from failed commands
• SessionStart      → Loads knowledge at session start
• SessionEnd        → Checks for knowledge updates

These hooks make the Context Engine 100% automatic!
{BLUE}{'━' * 60}{NC}
""")


def _is_ce_hook_entry(entry: dict) -> bool:
    hooks = entry.get('hooks') or []
    hook_markers = (
        'hooks_UserPromptSubmit.sh',
        'hooks_PostToolUse_ErrorCapture.py',
        'hooks_SessionStart.sh',
        'hooks_SessionEnd.sh',
        'prompt_tracker.py',
    )
    for hook in hooks:
        cmd = hook.get('command', '') if isinstance(hook, dict) else ''
        if any(marker in cmd for marker in hook_markers):
            return True
    return False


def _normalize_hooks_list(hooks_list: list) -> list:
    """Normalize legacy hook list entries to object form."""
    normalized = []
    for entry in hooks_list:
        if not isinstance(entry, dict):
            continue
        matcher = entry.get('matcher', {})
        hooks = entry.get('hooks', [])
        if isinstance(hooks, list):
            new_hooks = []
            for hook in hooks:
                if isinstance(hook, str):
                    new_hooks.append({"type": "command", "command": hook})
                elif isinstance(hook, dict):
                    new_hooks.append(hook)
            hooks = new_hooks
        new_entry = dict(entry)
        new_entry["hooks"] = hooks
        if matcher is None:
            matcher = {}
        new_entry["matcher"] = matcher
        normalized.append(new_entry)
    return normalized


def setup_hooks(force: bool = False):
    """Setup hooks in Claude Code settings"""
    settings_path = get_claude_settings_path()
    ce_root = get_ce_root()

    # Read existing settings
    settings = {}
    if settings_path.exists():
        try:
            with open(settings_path, 'r') as f:
                settings = json.load(f)
        except json.JSONDecodeError:
            settings = {}

    # Merge hooks
    hooks_config = generate_hooks_config(ce_root)

    if 'hooks' not in settings or not isinstance(settings.get('hooks'), dict):
        settings['hooks'] = {}

    for hook_name, hook_list in hooks_config['hooks'].items():
        existing = settings['hooks'].get(hook_name, [])
        existing = _normalize_hooks_list(existing)

        if force:
            preserved = [entry for entry in existing if not _is_ce_hook_entry(entry)]
            settings['hooks'][hook_name] = hook_list + preserved
        else:
            if not any(_is_ce_hook_entry(entry) for entry in existing):
                settings['hooks'][hook_name] = hook_list + existing
            else:
                settings['hooks'][hook_name] = existing

    # Ensure directory exists
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    # Write settings
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)

    print(f"{GREEN}✓{NC} Hooks configured in {settings_path}")
    return True


def main():
    import sys

    force = '--force' in sys.argv
    if '--show' in sys.argv:
        print_manual_setup()
        return

    print(f"\n{BLUE}Setting up Claude Code hooks...{NC}\n")
    try:
        setup_hooks(force=force)
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
