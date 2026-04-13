"""
Voice IME — Text Injector Module
Injects refined text into the active application via clipboard simulation.
"""

import logging
import time
import sys
from typing import Optional

logger = logging.getLogger("voice-ime.injector")


class TextInjector:
    """
    Injects text into the currently active application by:
    1. Saving the current clipboard content
    2. Copying the new text to clipboard
    3. Simulating Ctrl+V (Windows) or Cmd+V (macOS)
    4. Restoring the previous clipboard content
    """

    def __init__(self, config):
        """
        Args:
            config: AppConfig instance
        """
        self.config = config
        self._is_windows = sys.platform == "win32"

    def inject(self, text: str) -> bool:
        """
        Inject text into the active application.
        
        Args:
            text: The text to inject
            
        Returns:
            True if injection was successful
        """
        if not text or not text.strip():
            logger.warning("Empty text, nothing to inject")
            return False
        
        try:
            import pyperclip
            from pynput.keyboard import Controller, Key
            
            keyboard = Controller()
            
            # Step 1: Save current clipboard
            try:
                previous_clipboard = pyperclip.paste()
            except Exception:
                previous_clipboard = None
            
            # Step 2: Copy new text to clipboard
            pyperclip.copy(text)
            time.sleep(0.05)  # Small delay to ensure clipboard is set
            
            # Step 3: Simulate paste
            if self._is_windows:
                # Ctrl+V on Windows
                keyboard.press(Key.ctrl)
                keyboard.press('v')
                keyboard.release('v')
                keyboard.release(Key.ctrl)
            else:
                # Cmd+V on macOS
                keyboard.press(Key.cmd)
                keyboard.press('v')
                keyboard.release('v')
                keyboard.release(Key.cmd)
            
            logger.info(f"Injected {len(text)} chars into active application")
            
            # Step 4: Restore previous clipboard after a brief delay
            time.sleep(0.3)  # Wait for paste to complete
            if previous_clipboard is not None:
                try:
                    pyperclip.copy(previous_clipboard)
                except Exception:
                    pass  # Best effort restoration
            
            return True
            
        except Exception as e:
            logger.error(f"Text injection failed: {e}")
            return False

    def copy_to_clipboard(self, text: str) -> bool:
        """
        Simply copy text to clipboard without pasting.
        
        Args:
            text: The text to copy
            
        Returns:
            True if successful
        """
        try:
            import pyperclip
            pyperclip.copy(text)
            logger.info(f"Copied {len(text)} chars to clipboard")
            return True
        except Exception as e:
            logger.error(f"Clipboard copy failed: {e}")
            return False
