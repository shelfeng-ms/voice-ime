# Voice IME

A **100% local** voice input method for Windows and macOS. Speak into your microphone and have polished, well-formatted text injected into any active application.

## How It Works

```
🎤 Microphone → Silero VAD → faster-whisper (STT) → Gemma 4 (refinement) → 📋 Clipboard paste
```

1. **Press a hotkey** (`Ctrl+Alt+R`) to start/stop recording
2. **Speak naturally** — Voice Activity Detection handles start/stop automatically
3. **Whisper transcribes** your speech to text locally
4. **Gemma 4 refines** the text (fixes grammar, punctuation, formatting)
5. **Text is pasted** into whatever app is currently active

**All processing happens locally — your voice data never leaves your machine.**

## Quick Start

### Prerequisites
- **Python 3.9+**
- **FFmpeg** (for audio processing)
- **Ollama** (for Gemma 4 text refinement)

### Setup

```powershell
# Windows
cd E:\Playground\voice-ime
.\setup_env.ps1

# Or manual setup:
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Pull the Gemma 4 model (requires Ollama running)
ollama pull gemma4:e4b
```

### Run

```powershell
.\venv\Scripts\Activate.ps1
python main.py
```

### CLI Options

| Flag | Description |
|---|---|
| `--no-overlay` | Disable the floating status window |
| `--no-refine` | Skip LLM refinement (raw STT output) |
| `--model tiny\|base\|small\|medium\|large-v3` | Whisper model size |
| `--language en\|zh\|ja\|...` | Force STT language (default: auto) |
| `--llm-model gemma4:e4b` | Ollama model for refinement |
| `--device cuda\|cpu` | Force inference device |

## Hotkeys

| Hotkey | Action |
|---|---|
| `Ctrl+Alt+R` (Win) / `Cmd+Alt+R` (Mac) | Toggle recording on/off |
| `Ctrl+Alt+V` (Win) / `Cmd+Alt+V` (Mac) | Push-to-talk (hold to record) |

## Architecture

```
voice-ime/
├── main.py              # Entry point + pipeline orchestration
├── config.py            # Settings & configuration
├── audio_capture.py     # Microphone stream + Silero VAD
├── speech_to_text.py    # faster-whisper wrapper
├── text_refiner.py      # Ollama/Gemma 4 text refinement
├── text_injector.py     # Clipboard + paste injection
├── ui/
│   ├── tray_icon.py     # System tray icon + menu
│   └── overlay.py       # Floating status overlay
├── assets/
│   └── icon.png         # Tray icon
├── requirements.txt     # Python dependencies
├── setup_env.ps1        # Windows setup script
└── README.md            # This file
```

## Configuration

Settings are stored at:
- **Windows**: `%APPDATA%/VoiceIME/config.json`
- **macOS**: `~/Library/Application Support/VoiceIME/config.json`

Default configuration is used on first run. Modify the JSON file to customize behavior.

## Hardware Recommendations

| Component | Minimum | Recommended |
|---|---|---|
| GPU | None (CPU works) | NVIDIA 6GB+ VRAM |
| RAM | 8 GB | 16 GB |
| Whisper model | `tiny` (CPU) | `small` (GPU) |
| Gemma model | `gemma4:e2b` | `gemma4:e4b` |

## Roadmap

- [x] Phase 1: Windows desktop MVP
- [ ] Phase 2: macOS support
- [ ] Phase 3: Android custom keyboard app

## License

MIT
