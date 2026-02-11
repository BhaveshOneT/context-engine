# Context Engine Claude Plugin

This package installs Context Engine as a Claude Code hook-based plugin with automatic startup on every session.

## Install

From a local clone:

```bash
bash /path/to/context-engine/sydney/plugin/install.sh
```

From GitHub:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/onethousand-ai/context-engine/main/plugin/install.sh)
```

## What it configures

- `SessionStart` -> `scripts/hooks_AutoSessionStart.sh`
- `UserPromptSubmit` -> `scripts/hooks_UserPromptSubmit.sh`
- `PostToolUse (Bash)` -> `scripts/hooks_PostToolUse_ErrorCapture.py`
- `SessionEnd` -> `scripts/hooks_SessionEnd.sh`

## Verify

```bash
bash ~/.claude/plugins/context-engine/scripts/hooks_AutoSessionStart.sh
~/.claude/plugins/context-engine/ce status
```

## Uninstall

```bash
bash ~/.claude/plugins/context-engine/plugin/uninstall.sh
```

Remove plugin files too:

```bash
CE_REMOVE_FILES=true bash ~/.claude/plugins/context-engine/plugin/uninstall.sh
```
