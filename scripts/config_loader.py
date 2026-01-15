#!/usr/bin/env python3
"""
Centralized configuration loader for context-engine
Loads config.yaml with caching and provides simple get() interface
"""

import yaml
from pathlib import Path
from typing import Any, Dict, Optional

# Find the memory directory (context-engine root)
SCRIPT_DIR = Path(__file__).parent
MEMORY_DIR = SCRIPT_DIR.parent
CONFIG_FILE = MEMORY_DIR / 'config.yaml'

# Cache for loaded config
_config_cache: Optional[Dict[str, Any]] = None

def load_config() -> Dict[str, Any]:
    """
    Load configuration from config.yaml with caching
    Returns dict with all config values
    """
    global _config_cache

    # Return cached config if available
    if _config_cache is not None:
        return _config_cache

    # Default config (fallback)
    defaults = {
        'template_injection': {
            'relevance_threshold': 0.3,
            'max_patterns': 3,
            'max_failures': 3,
            'max_decisions': 2
        },
        'semantic_search': {
            'model': 'BAAI/bge-large-en-v1.5',
            'cross_reference_threshold': 0.75
        },
        'extraction': {
            'discovery_trigger': 2,
            'phase_trigger': 1,
            'error_trigger': 2
        },
        'monitoring': {
            'idle_threshold_minutes': 5,
            'file_debounce_seconds': 2
        }
    }

    # Try to load user config
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                user_config = yaml.safe_load(f) or {}
                # Merge user config with defaults (user config takes precedence)
                _config_cache = {**defaults, **user_config}
                return _config_cache
        except Exception as e:
            print(f"Warning: Failed to load config.yaml: {e}")
            print("Using default configuration...")

    # Use defaults if no config file or loading failed
    _config_cache = defaults
    return _config_cache


def get(key_path: str, default: Any = None) -> Any:
    """
    Get configuration value using dot notation

    Examples:
        get('template_injection.relevance_threshold')  # Returns 0.3
        get('semantic_search.model')  # Returns model name
        get('nonexistent.key', 'fallback')  # Returns 'fallback'

    Args:
        key_path: Dot-separated path to config value
        default: Default value if key not found

    Returns:
        Configuration value or default
    """
    config = load_config()

    # Split key path and traverse config dict
    keys = key_path.split('.')
    value = config

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


def reload_config() -> Dict[str, Any]:
    """
    Force reload configuration from disk (clears cache)
    Useful if config.yaml is modified during runtime

    Returns:
        Newly loaded configuration
    """
    global _config_cache
    _config_cache = None
    return load_config()


# Convenience function for checking if key exists
def has(key_path: str) -> bool:
    """
    Check if configuration key exists

    Args:
        key_path: Dot-separated path to config value

    Returns:
        True if key exists, False otherwise
    """
    return get(key_path) is not None


if __name__ == '__main__':
    # Test the config loader
    print("Testing config_loader...")
    print(f"Config file: {CONFIG_FILE}")
    print(f"Exists: {CONFIG_FILE.exists()}")
    print()

    config = load_config()
    print("Loaded configuration:")
    print(yaml.dump(config, default_flow_style=False))
    print()

    print("Example get() calls:")
    print(f"  get('template_injection.relevance_threshold') = {get('template_injection.relevance_threshold')}")
    print(f"  get('semantic_search.model') = {get('semantic_search.model')}")
    print(f"  get('nonexistent.key', 'default') = {get('nonexistent.key', 'default')}")
    print(f"  has('template_injection.relevance_threshold') = {has('template_injection.relevance_threshold')}")
    print(f"  has('nonexistent.key') = {has('nonexistent.key')}")
