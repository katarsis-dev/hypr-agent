"""Personal memory — user profile that persists across conversations."""

from __future__ import annotations

from pathlib import Path

# Default location for the profile
PROFILE_DIR = Path.home() / ".hypr-agent"
PROFILE_FILE = PROFILE_DIR / "profile.md"

DEFAULT_PROFILE = """# Personal Profile
# Edit this file to teach the agent about you.
# Everything here is injected into the agent's context for every conversation.
# Restart not needed — changes are picked up on the next message.

## About Me
- Name: 
- Location: 
- Languages: 

## Preferences
- OS: Arch Linux + Hyprland
- Editor: 
- Shell: 
- Code style: 

## Projects
- Main project: 
- Project paths: ~/projects/

## Notes
# Add anything you want the agent to always know:
# - "I prefer minimal solutions"
# - "Always use pacman, not yay"
# - "My wifi interface is wlan0"
"""


def get_profile() -> str:
    """Read the user's profile. Returns empty string if none exists."""
    if PROFILE_FILE.exists():
        return PROFILE_FILE.read_text()
    return ""


def save_profile(content: str) -> None:
    """Save the user's profile."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_FILE.write_text(content)


def init_profile() -> str:
    """Create a default profile if none exists. Returns the profile content."""
    if not PROFILE_FILE.exists():
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        PROFILE_FILE.write_text(DEFAULT_PROFILE)
    return PROFILE_FILE.read_text()


def get_profile_path() -> str:
    """Return the path to the profile file."""
    return str(PROFILE_FILE)
