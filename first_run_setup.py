"""
Voice IME — First-Run Setup & Model Manager
Handles automatic downloading and verification of all required models and infrastructure.
Called on every startup to ensure everything is ready.
"""

import os
import sys
import json
import shutil
import urllib.request
import urllib.error
import zipfile
import logging
import threading
import time
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger("voice-ime.setup")


# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────

def _get_models_dir() -> Path:
    """Get the models directory."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"
    d = base / "VoiceIME" / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


MODELS_DIR = _get_models_dir()

# Model registry: name → (url, expected_file, size_desc)
WHISPER_MODELS = {
    "tiny": (
        "https://huggingface.co/Systran/faster-whisper-tiny/resolve/main/model.bin",
        "faster-whisper-tiny",
        "~75 MB"
    ),
    "base": (
        "https://huggingface.co/Systran/faster-whisper-base/resolve/main/model.bin",
        "faster-whisper-base",
        "~150 MB"
    ),
    "small": (
        "https://huggingface.co/Systran/faster-whisper-small/resolve/main/model.bin",
        "faster-whisper-small",
        "~500 MB"
    ),
}

# Ollama download URLs
OLLAMA_URLS = {
    "win32": "https://ollama.com/download/OllamaSetup.exe",
    "darwin": "https://ollama.com/download/Ollama-darwin.zip",
}


# ──────────────────────────────────────────────
# Download Helpers
# ──────────────────────────────────────────────

def _download_file(url: str, dest: Path, progress_callback: Optional[Callable] = None) -> bool:
    """Download a file with progress reporting."""
    try:
        logger.info(f"Downloading: {url}")
        logger.info(f"  → {dest}")

        req = urllib.request.Request(url, headers={"User-Agent": "VoiceIME/1.0"})
        response = urllib.request.urlopen(req, timeout=60)

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0
        chunk_size = 1024 * 256  # 256 KB chunks

        dest.parent.mkdir(parents=True, exist_ok=True)

        with open(dest, "wb") as f:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)

                if progress_callback and total_size > 0:
                    pct = int(downloaded * 100 / total_size)
                    progress_callback(pct, downloaded, total_size)

        logger.info(f"Download complete: {dest.name} ({downloaded / 1024 / 1024:.1f} MB)")
        return True

    except Exception as e:
        logger.error(f"Download failed: {e}")
        if dest.exists():
            dest.unlink()
        return False


# ──────────────────────────────────────────────
# Whisper Model
# ──────────────────────────────────────────────

def is_whisper_model_cached(model_size: str = "base") -> bool:
    """Check if faster-whisper has the model cached (it auto-downloads)."""
    # faster-whisper uses huggingface_hub which caches in ~/.cache/huggingface/
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    model_name = f"models--Systran--faster-whisper-{model_size}"
    return (cache_dir / model_name).exists()


def ensure_whisper_model(model_size: str = "base", progress_callback: Optional[Callable] = None):
    """
    Ensure the Whisper model is available.
    faster-whisper auto-downloads from HuggingFace on first use,
    but we trigger it explicitly here so the user sees progress.
    """
    if is_whisper_model_cached(model_size):
        logger.info(f"Whisper model '{model_size}' already cached")
        return True

    logger.info(f"Whisper model '{model_size}' not found — will download on first transcription")
    logger.info("faster-whisper will auto-download from HuggingFace hub")

    # Try to pre-download by loading the model
    try:
        if progress_callback:
            progress_callback(-1, 0, 0)  # Indeterminate
        from faster_whisper import WhisperModel
        logger.info(f"Pre-downloading Whisper '{model_size}' model...")
        _ = WhisperModel(model_size, device="cpu", compute_type="int8")
        logger.info("Whisper model downloaded and verified")
        return True
    except Exception as e:
        logger.warning(f"Could not pre-download Whisper model: {e}")
        logger.info("Model will be downloaded on first use")
        return False


# ──────────────────────────────────────────────
# Silero VAD Model
# ──────────────────────────────────────────────

def is_silero_vad_cached() -> bool:
    """Check if Silero VAD is cached."""
    cache_dir = Path.home() / ".cache" / "torch" / "hub" / "snakers4_silero-vad_master"
    return cache_dir.exists()


def ensure_silero_vad(progress_callback: Optional[Callable] = None):
    """Pre-download Silero VAD model if not cached."""
    if is_silero_vad_cached():
        logger.info("Silero VAD model already cached")
        return True

    logger.info("Downloading Silero VAD model...")
    try:
        if progress_callback:
            progress_callback(-1, 0, 0)  # Indeterminate

        import torch
        torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False,
            trust_repo=True
        )
        logger.info("Silero VAD model downloaded")
        return True
    except Exception as e:
        logger.error(f"Failed to download Silero VAD: {e}")
        return False


# ──────────────────────────────────────────────
# Ollama
# ──────────────────────────────────────────────

def is_ollama_installed() -> bool:
    """Check if Ollama is installed."""
    if sys.platform == "win32":
        # Check common install locations
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Ollama" / "ollama.exe",
            shutil.which("ollama"),
        ]
        return any(c and Path(c).exists() if c else False for c in candidates)
    else:
        return shutil.which("ollama") is not None


def is_ollama_running() -> bool:
    """Check if Ollama server is running."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def is_ollama_model_available(model: str = "gemma4:e4b") -> bool:
    """Check if a specific model is downloaded in Ollama."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            models = [m.get("name", "") for m in data.get("models", [])]
            # Check both exact match and prefix match
            return any(model in m or m.startswith(model.split(":")[0]) for m in models)
    except Exception:
        return False


def download_ollama(progress_callback: Optional[Callable] = None) -> Optional[Path]:
    """Download Ollama installer."""
    if sys.platform not in OLLAMA_URLS:
        logger.error(f"No Ollama download URL for {sys.platform}")
        return None

    url = OLLAMA_URLS[sys.platform]
    ext = ".exe" if sys.platform == "win32" else ".zip"
    dest = MODELS_DIR / f"OllamaSetup{ext}"

    if dest.exists():
        logger.info(f"Ollama installer already downloaded: {dest}")
        return dest

    success = _download_file(url, dest, progress_callback)
    return dest if success else None


def install_ollama_windows(installer_path: Path):
    """Run the Ollama installer silently on Windows."""
    import subprocess
    logger.info("Installing Ollama...")
    try:
        # /VERYSILENT for Inno Setup installer
        result = subprocess.run(
            [str(installer_path), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
            timeout=120,
            capture_output=True
        )
        if result.returncode == 0:
            logger.info("Ollama installed successfully")
            return True
        else:
            logger.error(f"Ollama installer returned code {result.returncode}")
            return False
    except Exception as e:
        logger.error(f"Failed to install Ollama: {e}")
        return False


def pull_ollama_model(model: str = "gemma4:e4b", progress_callback: Optional[Callable] = None):
    """Pull an Ollama model."""
    try:
        logger.info(f"Pulling Ollama model: {model}...")
        if progress_callback:
            progress_callback(-1, 0, 0)

        data = json.dumps({"name": model, "stream": True}).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/pull",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=1800) as resp:  # 30 min timeout
            for line in resp:
                try:
                    status = json.loads(line.decode().strip())
                    if "total" in status and "completed" in status:
                        total = status["total"]
                        completed = status["completed"]
                        if total > 0 and progress_callback:
                            pct = int(completed * 100 / total)
                            progress_callback(pct, completed, total)
                    if status.get("status") == "success":
                        logger.info(f"Model '{model}' pulled successfully")
                        return True
                except json.JSONDecodeError:
                    continue

        return True

    except Exception as e:
        logger.error(f"Failed to pull model '{model}': {e}")
        return False


# ──────────────────────────────────────────────
# First-Run Setup (UI)
# ──────────────────────────────────────────────

class SetupWizard:
    """
    First-run setup wizard that downloads and verifies all required models.
    Shows a Tkinter progress window.
    """

    def __init__(self, config):
        self.config = config
        self._root = None
        self._status_label = None
        self._progress_var = None
        self._progress_bar = None
        self._detail_label = None
        self._done = False
        self._success = True

    def run(self) -> bool:
        """
        Run the setup wizard. Returns True if all required models are ready.
        Skips silently if everything is already cached.
        """
        # Quick check — if everything is ready, skip the wizard entirely
        if self._all_ready():
            logger.info("All models and infrastructure ready — skipping setup wizard")
            return True

        logger.info("Running first-time setup wizard...")

        # Run setup in background, show UI
        import tkinter as tk
        from tkinter import ttk

        self._root = tk.Tk()
        self._root.title("Voice IME — Setup")
        self._root.geometry("480x300")
        self._root.resizable(False, False)
        self._root.attributes("-topmost", True)
        self._root.configure(bg="#1e1e2e")

        # Center on screen
        self._root.update_idletasks()
        x = (self._root.winfo_screenwidth() // 2) - 240
        y = (self._root.winfo_screenheight() // 2) - 150
        self._root.geometry(f"+{x}+{y}")

        main = tk.Frame(self._root, bg="#1e1e2e", padx=30, pady=20)
        main.pack(fill="both", expand=True)

        tk.Label(
            main, text="Voice IME Setup",
            fg="#89b4fa", bg="#1e1e2e", font=("Segoe UI", 16, "bold")
        ).pack(anchor="w", pady=(0, 4))

        tk.Label(
            main, text="Downloading required models and checking infrastructure...",
            fg="#6c7086", bg="#1e1e2e", font=("Segoe UI", 10)
        ).pack(anchor="w", pady=(0, 20))

        self._status_label = tk.Label(
            main, text="Initializing...",
            fg="#cdd6f4", bg="#1e1e2e", font=("Segoe UI", 11)
        )
        self._status_label.pack(anchor="w", pady=(0, 8))

        self._progress_var = tk.DoubleVar(value=0)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Custom.Horizontal.TProgressbar",
                        troughcolor="#313244", background="#89b4fa",
                        darkcolor="#89b4fa", lightcolor="#89b4fa", bordercolor="#1e1e2e")

        self._progress_bar = ttk.Progressbar(
            main, variable=self._progress_var, maximum=100,
            style="Custom.Horizontal.TProgressbar", length=420
        )
        self._progress_bar.pack(fill="x", pady=(0, 8))

        self._detail_label = tk.Label(
            main, text="",
            fg="#6c7086", bg="#1e1e2e", font=("Segoe UI", 9)
        )
        self._detail_label.pack(anchor="w")

        # Start setup in background thread
        threading.Thread(target=self._run_setup, daemon=True).start()

        # Poll for completion
        self._poll()
        self._root.mainloop()

        return self._success

    def _all_ready(self) -> bool:
        """Check if all models are already cached."""
        whisper_ok = is_whisper_model_cached(self.config.whisper.model_size)
        vad_ok = is_silero_vad_cached()
        # Ollama/Gemma is optional — don't block on it
        return whisper_ok and vad_ok

    def _run_setup(self):
        """Background thread: run all setup steps."""
        try:
            steps = [
                ("Checking Silero VAD model...", self._step_silero_vad),
                ("Checking Whisper model...", self._step_whisper),
                ("Checking Ollama...", self._step_ollama),
            ]

            for i, (label, step_fn) in enumerate(steps):
                base_pct = int(i * 100 / len(steps))
                self._update_ui(label, base_pct)
                step_fn(base_pct, 100 // len(steps))

            self._update_ui("Setup complete!", 100)

        except Exception as e:
            logger.error(f"Setup error: {e}")
            self._update_ui(f"Error: {e}", 0)
            self._success = False

        self._done = True

    def _step_silero_vad(self, base_pct, pct_range):
        if is_silero_vad_cached():
            self._update_ui("Silero VAD: cached", base_pct + pct_range)
        else:
            self._update_ui("Downloading Silero VAD model...", base_pct)
            ensure_silero_vad()
            self._update_ui("Silero VAD: ready", base_pct + pct_range)

    def _step_whisper(self, base_pct, pct_range):
        model = self.config.whisper.model_size
        if is_whisper_model_cached(model):
            self._update_ui(f"Whisper ({model}): cached", base_pct + pct_range)
        else:
            self._update_ui(f"Downloading Whisper {model} model (this may take a few minutes)...", base_pct)

            def on_progress(pct, downloaded, total):
                if pct >= 0:
                    actual_pct = base_pct + int(pct * pct_range / 100)
                    size_mb = downloaded / 1024 / 1024
                    total_mb = total / 1024 / 1024
                    self._update_ui(
                        f"Downloading Whisper {model}: {size_mb:.0f}/{total_mb:.0f} MB",
                        actual_pct, f"{pct}%"
                    )

            ensure_whisper_model(model, on_progress)
            self._update_ui(f"Whisper ({model}): ready", base_pct + pct_range)

    def _step_ollama(self, base_pct, pct_range):
        if not self.config.llm.enabled:
            self._update_ui("LLM refinement: disabled (skipping Ollama)", base_pct + pct_range)
            return

        # Check if Ollama is installed
        if not is_ollama_installed():
            self._update_ui("Downloading Ollama installer...", base_pct)
            installer = download_ollama(
                lambda pct, dl, tot: self._update_ui(
                    f"Downloading Ollama: {dl // 1024 // 1024}MB",
                    base_pct + int(pct * pct_range / 300)  # 1/3 of range
                ) if pct >= 0 else None
            )
            if installer and sys.platform == "win32":
                self._update_ui("Installing Ollama (this may take a minute)...", base_pct + pct_range // 3)
                install_ollama_windows(installer)

        # Check if Ollama is running
        if is_ollama_installed() and not is_ollama_running():
            self._update_ui("Starting Ollama server...", base_pct + pct_range // 2)
            self._start_ollama()
            time.sleep(3)  # Wait for server to start

        # Check if model is available
        model = self.config.llm.model
        if is_ollama_running() and not is_ollama_model_available(model):
            self._update_ui(f"Pulling {model} (this may take several minutes)...", base_pct + pct_range // 2)
            pull_ollama_model(
                model,
                lambda pct, dl, tot: self._update_ui(
                    f"Pulling {model}: {pct}%",
                    base_pct + pct_range // 2 + int(pct * pct_range / 200)
                ) if pct >= 0 else None
            )

        if is_ollama_running() and is_ollama_model_available(model):
            self._update_ui(f"Ollama + {model}: ready", base_pct + pct_range)
        elif is_ollama_installed():
            self._update_ui(f"Ollama installed (start it manually: 'ollama serve')", base_pct + pct_range)
        else:
            self._update_ui("Ollama: not available (text refinement will be disabled)", base_pct + pct_range)
            self.config.llm.enabled = False

    def _start_ollama(self):
        """Try to start Ollama server."""
        import subprocess
        try:
            if sys.platform == "win32":
                # Try common locations
                candidates = [
                    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
                    shutil.which("ollama"),
                ]
                for c in candidates:
                    if c and Path(c).exists():
                        subprocess.Popen(
                            [str(c), "serve"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        logger.info(f"Started Ollama from {c}")
                        return
            else:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
        except Exception as e:
            logger.warning(f"Could not start Ollama: {e}")

    def _update_ui(self, status: str, progress: int = 0, detail: str = ""):
        """Update the setup wizard UI (thread-safe)."""
        if self._root:
            try:
                self._root.after(0, lambda: self._apply_ui(status, progress, detail))
            except Exception:
                pass

    def _apply_ui(self, status, progress, detail):
        if self._status_label:
            self._status_label.config(text=status)
        if self._progress_var is not None:
            self._progress_var.set(progress)
        if self._detail_label:
            self._detail_label.config(text=detail)

    def _poll(self):
        """Poll for setup completion."""
        if self._done:
            time.sleep(1)  # Brief pause so user sees "Setup complete!"
            if self._root:
                self._root.destroy()
            return
        if self._root:
            self._root.after(200, self._poll)


def run_setup(config) -> bool:
    """
    Entry point: run the setup wizard if needed.
    Returns True if all critical models are ready.
    """
    wizard = SetupWizard(config)
    return wizard.run()
