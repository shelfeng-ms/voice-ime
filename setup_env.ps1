# Voice IME — Environment Setup Script (Windows)
# Run this script once to set up the development environment.

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Voice IME — Environment Setup (Windows)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$ProjectDir = $PSScriptRoot
Set-Location $ProjectDir

# ─────────────────────────────────────────────
# Step 1: Check Python
# ─────────────────────────────────────────────
Write-Host "[1/6] Checking Python..." -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "  ERROR: Python not found. Please install Python 3.9+." -ForegroundColor Red
    exit 1
}
$pyVersion = python --version 2>&1
Write-Host "  Found: $pyVersion" -ForegroundColor Green

# ─────────────────────────────────────────────
# Step 2: Create virtual environment
# ─────────────────────────────────────────────
Write-Host "[2/6] Creating virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path ".\venv")) {
    python -m venv venv
    Write-Host "  Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "  Virtual environment already exists" -ForegroundColor Green
}

# Activate venv
.\venv\Scripts\Activate.ps1

# ─────────────────────────────────────────────
# Step 3: Install Python dependencies
# ─────────────────────────────────────────────
Write-Host "[3/6] Installing Python dependencies..." -ForegroundColor Yellow
pip install --upgrade pip
pip install -r requirements.txt
Write-Host "  Dependencies installed" -ForegroundColor Green

# ─────────────────────────────────────────────
# Step 4: Check FFmpeg
# ─────────────────────────────────────────────
Write-Host "[4/6] Checking FFmpeg..." -ForegroundColor Yellow
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpeg) {
    Write-Host "  WARNING: FFmpeg not found." -ForegroundColor Yellow
    Write-Host "  Install via: winget install ffmpeg" -ForegroundColor Yellow
    Write-Host "  Or download from: https://ffmpeg.org/download.html" -ForegroundColor Yellow
} else {
    $ffVersion = ffmpeg -version 2>&1 | Select-Object -First 1
    Write-Host "  Found: $ffVersion" -ForegroundColor Green
}

# ─────────────────────────────────────────────
# Step 5: Check Ollama
# ─────────────────────────────────────────────
Write-Host "[5/6] Checking Ollama..." -ForegroundColor Yellow
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host "  WARNING: Ollama not found." -ForegroundColor Yellow
    Write-Host "  Install from: https://ollama.com/download" -ForegroundColor Yellow
    Write-Host "  After installing, run: ollama pull gemma4:e4b" -ForegroundColor Yellow
} else {
    Write-Host "  Ollama found. Checking for Gemma 4 model..." -ForegroundColor Green
    $models = ollama list 2>&1
    if ($models -match "gemma4") {
        Write-Host "  Gemma 4 model is available" -ForegroundColor Green
    } else {
        Write-Host "  Gemma 4 not found. Pulling model..." -ForegroundColor Yellow
        Write-Host "  Run: ollama pull gemma4:e4b" -ForegroundColor Yellow
    }
}

# ─────────────────────────────────────────────
# Step 6: Check NVIDIA GPU
# ─────────────────────────────────────────────
Write-Host "[6/6] Checking GPU..." -ForegroundColor Yellow
try {
    $gpu = python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name(0)}') if torch.cuda.is_available() else None" 2>&1
    Write-Host "  $gpu" -ForegroundColor Green
} catch {
    Write-Host "  Could not detect GPU (will use CPU mode)" -ForegroundColor Yellow
}

# ─────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To start Voice IME:" -ForegroundColor White
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "  python main.py" -ForegroundColor White
Write-Host ""
Write-Host "Hotkey: Ctrl+Alt+R to toggle recording" -ForegroundColor White
Write-Host ""
