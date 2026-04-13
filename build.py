"""
Voice IME — PyInstaller Build Script
Builds the application into a standalone Windows .exe
"""

import PyInstaller.__main__
import os
import sys

# Get the project directory
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

PyInstaller.__main__.run([
    os.path.join(PROJECT_DIR, 'main.py'),
    
    # App metadata
    '--name=VoiceIME',
    '--windowed',                      # No console window
    f'--icon={os.path.join(PROJECT_DIR, "assets", "icon.png")}',
    
    # Include data files
    f'--add-data={os.path.join(PROJECT_DIR, "assets")}' + os.pathsep + 'assets',
    
    # Hidden imports that PyInstaller might miss
    '--hidden-import=pynput.keyboard._win32',
    '--hidden-import=pynput.mouse._win32',
    '--hidden-import=faster_whisper',
    '--hidden-import=ctranslate2',
    '--hidden-import=sounddevice',
    '--hidden-import=pystray._win32',
    '--hidden-import=PIL._tkinter_finder',
    '--hidden-import=torch',
    '--hidden-import=torchaudio',
    
    # Output directory
    f'--distpath={os.path.join(PROJECT_DIR, "dist")}',
    f'--workpath={os.path.join(PROJECT_DIR, "build")}',
    f'--specpath={PROJECT_DIR}',
    
    # One directory mode (faster startup than one-file, more reliable)
    '--onedir',
    
    # Don't ask for confirmation
    '--noconfirm',
    
    # Clean build
    '--clean',
])
