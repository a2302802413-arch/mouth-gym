from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
AUDIO_DIR = DATA_DIR / "audio"
LEGACY_CONFIG_PATH = DATA_DIR / "config.json"

PREP_SECONDS = 30
RESEARCH_SECONDS = 10 * 60
DEFAULT_SPEECH_SECONDS = 60
ALLOWED_SPEECH_SECONDS = {60, 120, 180}


def clear_legacy_config() -> None:
    """Remove legacy API credentials and AI settings from the old config file."""
    if LEGACY_CONFIG_PATH.exists():
        LEGACY_CONFIG_PATH.write_text("{}\n", encoding="utf-8")
