"""
Voice IME — Floating Overlay Module
Shows a small transparent overlay indicating the current state.
"""

import logging
import threading
import time
import sys

logger = logging.getLogger("voice-ime.overlay")


# Status messages and their emoji
STATUS_DISPLAY = {
    "idle": ("Ready", "⚪"),
    "listening": ("Listening...", "🎤"),
    "processing": ("Transcribing...", "⏳"),
    "refining": ("Refining...", "✨"),
    "done": ("Done!", "✅"),
    "error": ("Error", "❌"),
}

# Status → background color
STATUS_COLORS_TK = {
    "idle": "#2d2d2d",
    "listening": "#c0392b",
    "processing": "#2980b9",
    "refining": "#8e44ad",
    "done": "#27ae60",
    "error": "#c0392b",
}


class Overlay:
    """
    A small floating overlay window that shows the current Voice IME status.
    Uses Tkinter for cross-platform compatibility.
    """

    def __init__(self, config):
        """
        Args:
            config: AppConfig instance
        """
        self.config = config
        self._root = None
        self._label = None
        self._thread = None
        self._running = False
        self._auto_hide_timer = None
        self._current_status = "idle"

    def start(self):
        """Start the overlay in a background thread."""
        if not self.config.ui.show_overlay:
            logger.info("Overlay is disabled in config")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """Run the Tkinter overlay (blocking)."""
        try:
            import tkinter as tk
            
            self._root = tk.Tk()
            self._root.title("Voice IME")
            
            # Make it a floating overlay
            self._root.overrideredirect(True)           # No title bar
            self._root.attributes("-topmost", True)     # Always on top
            self._root.attributes("-alpha", self.config.ui.overlay_opacity)
            
            # Transparent background (Windows)
            if sys.platform == "win32":
                self._root.attributes("-transparentcolor", "#000001")
            
            # Position
            self._position_window()
            
            # Create label
            self._label = tk.Label(
                self._root,
                text="⚪ Voice IME Ready",
                font=("Segoe UI", 11, "bold") if sys.platform == "win32" else ("SF Pro", 11, "bold"),
                fg="white",
                bg="#2d2d2d",
                padx=16,
                pady=8,
                relief="flat",
            )
            self._label.pack(fill="both", expand=True)
            
            # Add rounded appearance with frame
            self._root.configure(bg="#2d2d2d")
            
            # Start hidden
            self._root.withdraw()
            
            logger.info("Overlay window created")
            self._root.mainloop()
            
        except Exception as e:
            logger.error(f"Overlay failed to start: {e}")
            self._running = False

    def _position_window(self):
        """Position the overlay window based on config."""
        if not self._root:
            return
        
        # Get screen dimensions
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        
        win_w = 260
        win_h = 44
        margin = 20
        
        position = self.config.ui.overlay_position
        
        if position == "top-right":
            x = screen_w - win_w - margin
            y = margin
        elif position == "top-left":
            x = margin
            y = margin
        elif position == "bottom-right":
            x = screen_w - win_w - margin
            y = screen_h - win_h - margin - 48  # Account for taskbar
        elif position == "bottom-left":
            x = margin
            y = screen_h - win_h - margin - 48
        else:
            x = screen_w - win_w - margin
            y = margin
        
        self._root.geometry(f"{win_w}x{win_h}+{x}+{y}")

    def update_status(self, status: str):
        """Update the overlay to show the current status."""
        self._current_status = status
        
        if not self._root or not self._label:
            return
        
        try:
            display_text, emoji = STATUS_DISPLAY.get(status, ("Unknown", "❓"))
            bg_color = STATUS_COLORS_TK.get(status, "#2d2d2d")
            
            def _update():
                if not self._label:
                    return
                self._label.config(
                    text=f" {emoji}  {display_text}",
                    bg=bg_color,
                )
                self._root.configure(bg=bg_color)
                
                # Show the overlay
                self._root.deiconify()
                self._root.lift()
                
                # Cancel any pending auto-hide
                if self._auto_hide_timer:
                    self._root.after_cancel(self._auto_hide_timer)
                    self._auto_hide_timer = None
                
                # Auto-hide for terminal states
                if status in ("done", "error", "idle"):
                    hide_ms = self.config.ui.overlay_auto_hide_ms
                    self._auto_hide_timer = self._root.after(hide_ms, self._hide)
            
            self._root.after(0, _update)
            
        except Exception as e:
            logger.error(f"Failed to update overlay: {e}")

    def _hide(self):
        """Hide the overlay."""
        if self._root:
            try:
                self._root.withdraw()
            except Exception:
                pass

    def stop(self):
        """Stop the overlay."""
        self._running = False
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass
