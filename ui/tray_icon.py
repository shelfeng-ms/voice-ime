"""
Voice IME — System Tray Icon Module
Provides a system tray icon with menu for the Voice IME application.
"""

import logging
import threading
import sys
from typing import Optional, Callable

logger = logging.getLogger("voice-ime.tray")


# Status → icon color mapping
STATUS_LABELS = {
    "idle": "Voice IME — Ready",
    "listening": "Voice IME — 🎤 Listening...",
    "processing": "Voice IME — ⏳ Processing...",
    "refining": "Voice IME — ✨ Refining...",
    "done": "Voice IME — ✅ Done!",
    "error": "Voice IME — ❌ Error",
}

# Status → icon color (R, G, B)
STATUS_COLORS = {
    "idle": (100, 100, 100),      # Gray
    "listening": (220, 50, 50),    # Red
    "processing": (50, 130, 220),  # Blue
    "refining": (180, 100, 220),   # Purple
    "done": (50, 180, 80),         # Green
    "error": (220, 50, 50),        # Red
}


def _create_icon_image(color=(100, 100, 100), size=64):
    """Create a simple circular icon image with the given color."""
    from PIL import Image, ImageDraw
    
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw filled circle
    margin = 4
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=color + (255,),
        outline=(255, 255, 255, 200),
        width=2
    )
    
    # Draw microphone icon (simplified as lines)
    cx, cy = size // 2, size // 2
    mic_w = size // 6
    mic_h = size // 4
    
    # Mic body
    draw.rounded_rectangle(
        [cx - mic_w, cy - mic_h, cx + mic_w, cy + mic_h // 2],
        radius=mic_w,
        fill=(255, 255, 255, 220)
    )
    
    # Mic stand
    draw.line(
        [(cx, cy + mic_h // 2 + 2), (cx, cy + mic_h)],
        fill=(255, 255, 255, 220),
        width=2
    )
    draw.line(
        [(cx - mic_w, cy + mic_h), (cx + mic_w, cy + mic_h)],
        fill=(255, 255, 255, 220),
        width=2
    )
    
    return img


class TrayIcon:
    """
    System tray icon for Voice IME.
    Provides visual status feedback and a context menu.
    """

    def __init__(self, on_toggle_recording=None, on_toggle_refinement=None, on_settings=None, on_quit=None):
        """
        Args:
            on_toggle_recording: Callback when user clicks Start/Stop Recording
            on_toggle_refinement: Callback when user toggles LLM refinement
            on_settings: Callback when user clicks Settings
            on_quit: Callback when user clicks Quit
        """
        self.on_toggle_recording = on_toggle_recording
        self.on_toggle_refinement = on_toggle_refinement
        self.on_settings = on_settings
        self.on_quit = on_quit
        
        self._icon = None
        self._status = "idle"
        self._is_recording = False
        self._refinement_enabled = True
        self._thread = None

    def start(self):
        """Start the tray icon in a background thread."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """Run the tray icon (blocking)."""
        import pystray
        
        menu = pystray.Menu(
            pystray.MenuItem(
                lambda item: "Stop Recording" if self._is_recording else "Start Recording",
                self._on_toggle_recording,
                default=True  # Double-click action
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: "LLM Refinement  [ON]" if self._refinement_enabled else "LLM Refinement  [OFF]",
                self._on_toggle_refinement,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings...", self._on_settings),
            pystray.MenuItem("About", self._on_about),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        )
        
        self._icon = pystray.Icon(
            "voice-ime",
            icon=_create_icon_image(STATUS_COLORS["idle"]),
            title=STATUS_LABELS["idle"],
            menu=menu,
        )
        
        logger.info("System tray icon started")
        self._icon.run()

    def update_status(self, status: str):
        """Update the tray icon to reflect current status."""
        self._status = status
        
        if status == "listening":
            self._is_recording = True
        elif status == "idle":
            self._is_recording = False
        
        if self._icon:
            try:
                color = STATUS_COLORS.get(status, STATUS_COLORS["idle"])
                self._icon.icon = _create_icon_image(color)
                self._icon.title = STATUS_LABELS.get(status, f"Voice IME — {status}")
                
                # Force menu refresh
                self._icon.update_menu()
            except Exception as e:
                logger.error(f"Failed to update tray icon: {e}")

    def set_refinement_enabled(self, enabled: bool):
        """Update the refinement toggle state."""
        self._refinement_enabled = enabled
        if self._icon:
            self._icon.update_menu()

    def stop(self):
        """Stop the tray icon."""
        if self._icon:
            self._icon.stop()
            logger.info("System tray icon stopped")

    def _on_toggle_recording(self, icon, item):
        if self.on_toggle_recording:
            self.on_toggle_recording()

    def _on_toggle_refinement(self, icon, item):
        self._refinement_enabled = not self._refinement_enabled
        if self.on_toggle_refinement:
            self.on_toggle_refinement(self._refinement_enabled)

    def _on_settings(self, icon, item):
        if self.on_settings:
            self.on_settings()

    def _on_about(self, icon, item):
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showinfo(
            "About Voice IME",
            "Voice IME v1.0\n\n"
            "Local voice input method\n"
            "Whisper (STT) + Gemma 4 (refinement)\n\n"
            "All processing stays on your machine.\n"
            "No data leaves your device.",
            parent=root
        )
        root.destroy()

    def _on_quit(self, icon, item):
        if self.on_quit:
            self.on_quit()
        self.stop()
