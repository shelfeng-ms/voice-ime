"""
Voice IME — macOS Permission Helper
Handles requesting and checking macOS permissions for Microphone and Accessibility.
"""

import sys
import subprocess
import logging

logger = logging.getLogger("voice-ime.macos")


def check_accessibility_permission() -> bool:
    """
    Check if the app has Accessibility permission on macOS.
    This is required for simulating keyboard input (Ctrl+V paste).
    """
    if sys.platform != "darwin":
        return True
    
    try:
        # Use AppleScript to test accessibility
        result = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to return name of first process'],
            capture_output=True, timeout=5
        )
        if result.returncode == 0:
            logger.info("Accessibility permission: granted")
            return True
        else:
            logger.warning("Accessibility permission: NOT granted")
            return False
    except Exception as e:
        logger.warning(f"Could not check accessibility permission: {e}")
        return False


def request_accessibility_permission():
    """
    Open System Settings to the Accessibility pane on macOS.
    The user needs to manually grant permission.
    """
    if sys.platform != "darwin":
        return
    
    try:
        subprocess.run([
            "open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
        ])
        logger.info("Opened System Settings > Accessibility")
    except Exception as e:
        logger.error(f"Failed to open System Settings: {e}")


def check_microphone_permission() -> bool:
    """
    Check if the app has Microphone permission on macOS.
    Note: The OS will auto-prompt on first use of the microphone.
    """
    if sys.platform != "darwin":
        return True
    
    # On macOS, the system will automatically prompt for microphone access
    # when sounddevice tries to open an audio stream. We just return True here
    # and let the OS handle the prompt.
    return True


def ensure_macos_permissions():
    """
    Check and request necessary macOS permissions.
    Called during app startup on macOS.
    """
    if sys.platform != "darwin":
        return
    
    logger.info("Checking macOS permissions...")
    
    # Check accessibility (needed for keyboard simulation)
    if not check_accessibility_permission():
        logger.warning(
            "Accessibility permission is required for Voice IME to paste text. "
            "Please grant access in System Settings > Privacy & Security > Accessibility"
        )
        request_accessibility_permission()
        
        # Show a dialog
        try:
            subprocess.run([
                "osascript", "-e",
                'display dialog "Voice IME needs Accessibility permission to paste text into apps.\\n\\n'
                'Please add this app in:\\nSystem Settings > Privacy & Security > Accessibility" '
                'with title "Voice IME" buttons {"OK"} default button "OK"'
            ], timeout=30)
        except Exception:
            pass
    
    logger.info("macOS permission check complete")
