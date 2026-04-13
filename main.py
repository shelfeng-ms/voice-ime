"""
Voice IME — Main Application
Entry point and pipeline orchestrator for the Voice Input Method.

Usage:
    python main.py              # Run with default settings
    python main.py --no-overlay # Run without the floating overlay
    python main.py --no-refine  # Run without LLM text refinement
"""

import sys
import time
import logging
import argparse
import threading
import numpy as np
from typing import Optional

from config import get_config, AppConfig
from audio_capture import AudioCapture
from speech_to_text import SpeechToText
from text_refiner import TextRefiner
from text_injector import TextInjector
from ui.tray_icon import TrayIcon
from ui.overlay import Overlay
from ui.settings_dialog import SettingsDialog


# ──────────────────────────────────────────────
# Logging Setup
# ──────────────────────────────────────────────

def setup_logging(console=True):
    """Configure logging for the application."""
    from config import LOG_DIR
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    log_format = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    date_format = "%H:%M:%S"
    
    # Root logger
    root_logger = logging.getLogger("voice-ime")
    root_logger.setLevel(logging.DEBUG)
    
    # Console handler — only if running with a visible console
    if console and sys.stdout is not None:
        try:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(logging.Formatter(log_format, date_format))
            root_logger.addHandler(console_handler)
        except Exception:
            pass  # No console available (windowed mode)
    
    # File handler — always active
    file_handler = logging.FileHandler(
        LOG_DIR / "voice-ime.log",
        encoding="utf-8",
        mode="a"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    root_logger.addHandler(file_handler)
    
    return root_logger


# ──────────────────────────────────────────────
# Application Class
# ──────────────────────────────────────────────

class VoiceIMEApp:
    """
    Main application orchestrator.
    
    Pipeline: Hotkey → Audio Capture → VAD → Whisper STT → Gemma Refinement → Text Injection
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.logger = logging.getLogger("voice-ime.app")
        
        # Core components
        self.stt = SpeechToText(config)
        self.refiner = TextRefiner(config)
        self.injector = TextInjector(config)
        self.audio = AudioCapture(config, on_speech_segment=self._on_speech_segment)
        
        # UI components
        self.tray = TrayIcon(
            on_toggle_recording=self._toggle_recording,
            on_toggle_refinement=self._toggle_refinement,
            on_settings=self._open_settings,
            on_quit=self._quit,
        )
        self.overlay = Overlay(config)
        
        # Wire up status callbacks
        self.audio.on_status_change = self._on_status_change
        
        # State
        self._running = False
        self._hotkey_listener = None

    def start(self):
        """Start the Voice IME application."""
        self.logger.info("=" * 60)
        self.logger.info("Voice IME starting...")
        self.logger.info(f"Platform: {sys.platform}")
        self.logger.info(f"Whisper model: {self.config.whisper.model_size}")
        self.logger.info(f"LLM: {self.config.llm.model} (enabled={self.config.llm.enabled})")
        self.logger.info(f"Hotkey mode: {self.config.hotkey.mode}")
        self.logger.info("=" * 60)
        
        self._running = True
        
        # macOS: check permissions before doing anything else
        if sys.platform == "darwin":
            from macos_permissions import ensure_macos_permissions
            ensure_macos_permissions()
        
        # First-run setup: download models and check infrastructure
        from first_run_setup import run_setup
        if not run_setup(self.config):
            self.logger.warning("Setup incomplete — some features may not work")
        
        # Pre-load the Whisper model (can take a few seconds)
        self.logger.info("Loading Whisper model (this may take a moment)...")
        self._on_status_change("processing")
        try:
            self.stt.load_model()
        except Exception as e:
            self.logger.error(f"Failed to load Whisper model: {e}")
            self.logger.error("Please ensure faster-whisper is installed: pip install faster-whisper")
            sys.exit(1)
        
        # Check Ollama availability
        if self.config.llm.enabled:
            self.logger.info("Checking Ollama availability...")
            if self.refiner.check_availability():
                self.logger.info("✅ Ollama is ready")
            else:
                self.logger.warning(
                    f"⚠️  Ollama not available. Text refinement will be skipped. "
                    f"Run: ollama pull {self.config.llm.model}"
                )
        
        # Start UI
        self.overlay.start()
        self.tray.start()
        
        # Register global hotkey
        self._register_hotkeys()
        
        self._on_status_change("idle")
        
        hotkey = self.config.hotkey.toggle_recording if self.config.hotkey.mode == "toggle" else self.config.hotkey.push_to_talk
        self.logger.info(f"✅ Voice IME is ready! Press {hotkey} to start/stop recording")
        
        # Keep the main thread alive
        try:
            while self._running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
            self._quit()

    def _register_hotkeys(self):
        """Register global hotkeys."""
        from pynput import keyboard
        
        hotkey_map = {}
        
        if self.config.hotkey.mode == "toggle":
            hotkey_map[self.config.hotkey.toggle_recording] = self._toggle_recording
        else:
            # Push-to-talk: press to start, release to stop
            hotkey_map[self.config.hotkey.push_to_talk] = self._toggle_recording
        
        self._hotkey_listener = keyboard.GlobalHotKeys(hotkey_map)
        self._hotkey_listener.start()
        
        self.logger.info(f"Global hotkeys registered: {list(hotkey_map.keys())}")

    def _toggle_recording(self):
        """Toggle audio recording on/off."""
        if self.audio.is_recording:
            self.logger.info("⏹ Stopping recording...")
            self.audio.stop()
        else:
            self.logger.info("🎤 Starting recording...")
            self.audio.start()

    def _toggle_refinement(self, enabled: bool):
        """Toggle LLM refinement on/off."""
        self.config.llm.enabled = enabled
        self.tray.set_refinement_enabled(enabled)
        status = "enabled" if enabled else "disabled"
        self.logger.info(f"LLM refinement {status}")

    def _open_settings(self):
        """Open the settings dialog."""
        self.logger.info("Opening settings dialog...")
        dialog = SettingsDialog(self.config, on_save=self._on_settings_saved)
        dialog.show()

    def _on_settings_saved(self, new_config: AppConfig):
        """Handle settings being saved."""
        self.logger.info("Settings updated — some changes take effect on next restart")
        self.tray.set_refinement_enabled(new_config.llm.enabled)

    def _on_speech_segment(self, audio: np.ndarray):
        """
        Called when a complete speech segment is detected.
        Runs the full pipeline: STT → Refinement → Injection.
        """
        pipeline_start = time.time()
        
        try:
            # Step 1: Speech-to-Text
            self._on_status_change("processing")
            raw_text = self.stt.transcribe(audio)
            
            if not raw_text or not raw_text.strip():
                self.logger.warning("Empty transcription result")
                self._on_status_change("idle")
                return
            
            self.logger.info(f"📝 Raw: {raw_text}")
            
            # Step 2: Text Refinement (optional)
            if self.config.llm.enabled and self.config.llm.refinement_level != "off":
                self._on_status_change("refining")
                refined_text = self.refiner.refine(raw_text)
            else:
                refined_text = raw_text
            
            if refined_text != raw_text:
                self.logger.info(f"✨ Refined: {refined_text}")
            
            # Step 3: Text Injection
            success = self.injector.inject(refined_text)
            
            if success:
                elapsed = time.time() - pipeline_start
                self.logger.info(f"✅ Pipeline complete in {elapsed:.1f}s")
                self._on_status_change("done")
            else:
                self._on_status_change("error")
            
        except Exception as e:
            self.logger.error(f"Pipeline error: {e}", exc_info=True)
            self._on_status_change("error")
        
        # Return to idle/listening based on recording state
        time.sleep(1.5)
        if self.audio.is_recording:
            self._on_status_change("listening")
        else:
            self._on_status_change("idle")

    def _on_status_change(self, status: str):
        """Handle status changes — update all UI components."""
        self.tray.update_status(status)
        self.overlay.update_status(status)

    def _quit(self):
        """Shut down the application."""
        self.logger.info("Shutting down Voice IME...")
        self._running = False
        
        # Stop components
        if self.audio.is_recording:
            self.audio.stop()
        
        if self._hotkey_listener:
            self._hotkey_listener.stop()
        
        self.overlay.stop()
        self.tray.stop()
        
        self.logger.info("Voice IME stopped. Goodbye!")


# ──────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Voice IME — Local voice input method using Whisper + Gemma 4"
    )
    parser.add_argument(
        "--no-overlay", action="store_true",
        help="Disable the floating status overlay"
    )
    parser.add_argument(
        "--no-refine", action="store_true",
        help="Disable LLM text refinement (raw STT output only)"
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Whisper model size: tiny, base, small, medium, large-v3"
    )
    parser.add_argument(
        "--language", type=str, default=None,
        help="Force language for STT (e.g., 'en', 'zh', 'ja'). Default: auto-detect"
    )
    parser.add_argument(
        "--llm-model", type=str, default=None,
        help="Ollama model name for text refinement (e.g., 'gemma4:e4b')"
    )
    parser.add_argument(
        "--device", type=str, default=None,
        help="Inference device: auto, cuda, cpu"
    )
    parser.add_argument(
        "--console", action="store_true",
        help="Show console window (for debugging)"
    )
    
    args = parser.parse_args()
    
    # Detect if we're running as a windowed app (no console)
    is_windowed = getattr(sys, 'frozen', False) or sys.stdout is None
    show_console = args.console or not is_windowed
    
    # Setup logging
    logger = setup_logging(console=show_console)
    
    # Load config
    config = get_config()
    
    # Apply CLI overrides
    if args.no_overlay:
        config.ui.show_overlay = False
    if args.no_refine:
        config.llm.enabled = False
    if args.model:
        config.whisper.model_size = args.model
    if args.language:
        config.whisper.language = args.language
    if args.llm_model:
        config.llm.model = args.llm_model
    if args.device:
        config.whisper.device = args.device
    
    # Create and start the app
    app = VoiceIMEApp(config)
    app.start()


if __name__ == "__main__":
    main()
