"""
Voice IME — Configuration Module
Central configuration for the Voice Input Method application.
"""

import sys
import os
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List


# ──────────────────────────────────────────────
# Platform Detection
# ──────────────────────────────────────────────

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

PLATFORM = "windows" if IS_WINDOWS else "macos" if IS_MACOS else "linux"


# ──────────────────────────────────────────────
# Default Paths
# ──────────────────────────────────────────────

if IS_WINDOWS:
    CONFIG_DIR = Path(os.environ.get("APPDATA", "~")) / "VoiceIME"
elif IS_MACOS:
    CONFIG_DIR = Path.home() / "Library" / "Application Support" / "VoiceIME"
else:
    CONFIG_DIR = Path.home() / ".config" / "voice-ime"

CONFIG_FILE = CONFIG_DIR / "config.json"
LOG_DIR = CONFIG_DIR / "logs"


# ──────────────────────────────────────────────
# Configuration Data Classes
# ──────────────────────────────────────────────

@dataclass
class AudioConfig:
    """Audio capture settings."""
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration_ms: int = 32          # VAD frame size: MUST be 32ms for 16kHz (Silero requires exactly 512 samples)
    silence_grace_ms: int = 800          # Wait this long after silence before triggering STT
    min_speech_duration_ms: int = 500    # Ignore segments shorter than this
    vad_threshold: float = 0.5           # Silero VAD confidence threshold (0.0 - 1.0)


@dataclass
class WhisperConfig:
    """Speech-to-text settings."""
    model_size: str = "base"             # tiny, base, small, medium, large-v3
    device: str = "cpu"                  # auto, cuda, cpu
    compute_type: str = "int8"           # auto, float16, int8, float32
    language: Optional[str] = None       # None = auto-detect, or "en", "zh", "ja", etc.
    beam_size: int = 5
    task: str = "transcribe"             # transcribe or translate


@dataclass
class LLMConfig:
    """Text refinement LLM settings."""
    enabled: bool = True
    ollama_base_url: str = "http://localhost:11434"
    model: str = "gemma4:e4b"            # Ollama model tag
    timeout_seconds: int = 30
    refinement_level: str = "light"      # off, light, full
    system_prompt_light: str = (
        "You are a text refinement assistant. The user dictated the following text "
        "via speech-to-text. Fix grammar, punctuation, and capitalization errors. "
        "Preserve the original meaning, tone, and language. "
        "Return ONLY the corrected text with no explanations or extra commentary."
    )
    system_prompt_full: str = (
        "You are a text refinement assistant. The user dictated the following text "
        "via speech-to-text. Rewrite it to be clear, well-structured, and professional "
        "while preserving the original meaning and language. Fix all grammar, punctuation, "
        "and formatting issues. Return ONLY the refined text with no explanations."
    )


@dataclass
class HotkeyConfig:
    """Global hotkey settings."""
    # Push-to-talk hotkey
    push_to_talk: str = "<ctrl>+<alt>+v" if IS_WINDOWS else "<cmd>+<alt>+v"
    # Toggle recording on/off
    toggle_recording: str = "<ctrl>+<alt>+r" if IS_WINDOWS else "<cmd>+<alt>+r"
    # Mode: 'push_to_talk' or 'toggle'
    mode: str = "toggle"


@dataclass
class UIConfig:
    """UI settings."""
    show_overlay: bool = True
    overlay_position: str = "top-right"  # top-left, top-right, bottom-left, bottom-right
    overlay_opacity: float = 0.85
    overlay_auto_hide_ms: int = 3000     # Hide overlay after this many ms


@dataclass
class UserPreferences:
    """User preferences for recognition and refinement."""
    # Custom vocabulary — names, acronyms, terms the models should know
    # These get injected into both Whisper's initial_prompt and the LLM system prompt
    custom_vocabulary: List[str] = field(default_factory=list)
    
    # Language preference:
    #   "auto"      — auto-detect language
    #   "en"        — English only
    #   "zh"        — Chinese only
    #   "en-zh"     — English-Chinese mixed (code-switching)
    #   "en-ja"     — English-Japanese mixed
    #   etc.
    language_preference: str = "auto"
    
    # Custom instructions for the LLM refinement (e.g., "Always use formal tone")
    custom_instructions: str = ""
    
    # Output formatting preference
    #   "natural"   — natural dictation flow
    #   "sentences" — add sentence punctuation
    #   "bullet"    — format as bullet points
    output_format: str = "sentences"


@dataclass
class AppConfig:
    """Root application configuration."""
    audio: AudioConfig = field(default_factory=AudioConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    preferences: UserPreferences = field(default_factory=UserPreferences)

    def save(self):
        """Save configuration to disk."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls) -> "AppConfig":
        """Load configuration from disk, or return defaults."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls(
                    audio=AudioConfig(**data.get("audio", {})),
                    whisper=WhisperConfig(**data.get("whisper", {})),
                    llm=LLMConfig(**data.get("llm", {})),
                    hotkey=HotkeyConfig(**data.get("hotkey", {})),
                    ui=UIConfig(**data.get("ui", {})),
                    preferences=UserPreferences(**data.get("preferences", {})),
                )
            except Exception as e:
                print(f"[config] Failed to load config: {e}, using defaults")
        return cls()


# ──────────────────────────────────────────────
# Singleton Config Instance
# ──────────────────────────────────────────────

_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get or initialize the global configuration."""
    global _config
    if _config is None:
        _config = AppConfig.load()
    return _config


def reset_config():
    """Reset to default configuration."""
    global _config
    _config = AppConfig()
    _config.save()
