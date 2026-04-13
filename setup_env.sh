#!/bin/bash
# Voice IME — Environment Setup Script (macOS)
# Run this script once to set up the development environment.

set -e

echo "============================================"
echo "  Voice IME — Environment Setup (macOS)"
echo "============================================"
echo ""

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# ─────────────────────────────────────────────
# Step 1: Check Python
# ─────────────────────────────────────────────
echo "[1/6] Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "  ERROR: Python 3 not found. Install via: brew install python@3.11"
    exit 1
fi
PY_VERSION=$(python3 --version 2>&1)
echo "  Found: $PY_VERSION"

# ─────────────────────────────────────────────
# Step 2: Create virtual environment
# ─────────────────────────────────────────────
echo "[2/6] Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  Virtual environment created"
else
    echo "  Virtual environment already exists"
fi

source venv/bin/activate

# ─────────────────────────────────────────────
# Step 3: Install Python dependencies
# ─────────────────────────────────────────────
echo "[3/6] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "  Dependencies installed"

# ─────────────────────────────────────────────
# Step 4: Check FFmpeg
# ─────────────────────────────────────────────
echo "[4/6] Checking FFmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "  WARNING: FFmpeg not found."
    echo "  Install via: brew install ffmpeg"
else
    FF_VERSION=$(ffmpeg -version 2>&1 | head -1)
    echo "  Found: $FF_VERSION"
fi

# ─────────────────────────────────────────────
# Step 5: Check Ollama
# ─────────────────────────────────────────────
echo "[5/6] Checking Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "  WARNING: Ollama not found."
    echo "  Install from: https://ollama.com/download"
    echo "  After installing, run: ollama pull gemma4:e4b"
else
    echo "  Ollama found. Checking for Gemma 4 model..."
    if ollama list 2>&1 | grep -q "gemma4"; then
        echo "  Gemma 4 model is available"
    else
        echo "  Gemma 4 not found. Run: ollama pull gemma4:e4b"
    fi
fi

# ─────────────────────────────────────────────
# Step 6: Check macOS Permissions
# ─────────────────────────────────────────────
echo "[6/6] macOS Permissions..."
echo "  Voice IME requires the following permissions:"
echo "    • Microphone: System Settings > Privacy & Security > Microphone"
echo "    • Accessibility: System Settings > Privacy & Security > Accessibility"
echo "  You will be prompted when you first run the app."

# Check Apple Silicon vs Intel
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    echo ""
    echo "  Detected Apple Silicon ($ARCH) — models will use Metal acceleration"
else
    echo ""
    echo "  Detected Intel ($ARCH) — models will use CPU"
fi

# ─────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────
echo ""
echo "============================================"
echo "  Setup complete!"
echo "============================================"
echo ""
echo "To start Voice IME:"
echo "  source venv/bin/activate"
echo "  python3 main.py"
echo ""
echo "Hotkey: Cmd+Option+R to toggle recording"
echo ""
