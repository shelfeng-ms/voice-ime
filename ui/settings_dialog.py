"""
Voice IME — Settings Dialog
A Tkinter-based settings window accessible from the system tray menu.
"""

import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from config import get_config, AppConfig

logger = logging.getLogger("voice-ime.settings")


class SettingsDialog:
    """Settings dialog for Voice IME configuration."""

    def __init__(self, config: AppConfig, on_save=None):
        self.config = config
        self.on_save = on_save
        self._root = None

    def show(self):
        """Show the settings dialog. Creates a new window each time."""
        thread = threading.Thread(target=self._build, daemon=True)
        thread.start()

    def _build(self):
        self._root = tk.Tk()
        self._root.title("Voice IME Settings")
        self._root.geometry("500x820")
        self._root.resizable(False, True)
        self._root.attributes("-topmost", True)

        # Styling
        bg = "#1e1e2e"
        fg = "#cdd6f4"
        accent = "#89b4fa"
        input_bg = "#313244"
        self._root.configure(bg=bg)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", background=bg, foreground=fg, font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=bg, foreground=accent, font=("Segoe UI", 12, "bold"))
        style.configure("TCombobox", fieldbackground=input_bg, foreground=fg, font=("Segoe UI", 10))
        style.configure("TCheckbutton", background=bg, foreground=fg, font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10, "bold"))
        style.configure("TScale", background=bg)
        style.configure("TFrame", background=bg)

        # Scrollable frame
        canvas = tk.Canvas(self._root, bg=bg, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self._root, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        main = ttk.Frame(canvas, padding=20)
        canvas.create_window((0, 0), window=main, anchor="nw")
        main.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        # Enable mouse wheel scrolling
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        row = 0

        # ── Whisper Settings ──
        ttk.Label(main, text="Speech-to-Text (Whisper)", style="Header.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        row += 1

        ttk.Label(main, text="Model Size:").grid(row=row, column=0, sticky="w", pady=4)
        self.whisper_model = ttk.Combobox(
            main, values=["tiny", "base", "small", "medium", "large-v3"],
            state="readonly", width=20
        )
        self.whisper_model.set(self.config.whisper.model_size)
        self.whisper_model.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(main, text="Language:").grid(row=row, column=0, sticky="w", pady=4)
        self.language = ttk.Combobox(
            main,
            values=["Auto Detect", "en (English)", "zh (Chinese)", "ja (Japanese)",
                    "ko (Korean)", "de (German)", "fr (French)", "es (Spanish)"],
            state="readonly", width=20
        )
        lang = self.config.whisper.language
        if lang is None:
            self.language.set("Auto Detect")
        else:
            # Find matching display string
            for v in self.language["values"]:
                if v.startswith(lang):
                    self.language.set(v)
                    break
            else:
                self.language.set("Auto Detect")
        self.language.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(main, text="Device:").grid(row=row, column=0, sticky="w", pady=4)
        self.device = ttk.Combobox(
            main, values=["cpu", "cuda", "auto"], state="readonly", width=20
        )
        self.device.set(self.config.whisper.device)
        self.device.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        # ── LLM Settings ──
        ttk.Label(main, text="Text Refinement (Gemma 4)", style="Header.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(16, 8)
        )
        row += 1

        self.llm_enabled_var = tk.BooleanVar(value=self.config.llm.enabled)
        ttk.Checkbutton(main, text="Enable LLM refinement", variable=self.llm_enabled_var).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=4
        )
        row += 1

        ttk.Label(main, text="Model:").grid(row=row, column=0, sticky="w", pady=4)
        self.llm_model = ttk.Combobox(
            main,
            values=["gemma4:e2b", "gemma4:e4b", "gemma4:12b", "gemma4:27b"],
            width=20
        )
        self.llm_model.set(self.config.llm.model)
        self.llm_model.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(main, text="Refinement Level:").grid(row=row, column=0, sticky="w", pady=4)
        self.refinement_level = ttk.Combobox(
            main, values=["off", "light", "full"], state="readonly", width=20
        )
        self.refinement_level.set(self.config.llm.refinement_level)
        self.refinement_level.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        # ── Audio Settings ──
        ttk.Label(main, text="Audio", style="Header.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(16, 8)
        )
        row += 1

        ttk.Label(main, text="VAD Sensitivity:").grid(row=row, column=0, sticky="w", pady=4)
        self.vad_threshold = tk.DoubleVar(value=self.config.audio.vad_threshold)
        vad_frame = ttk.Frame(main)
        vad_scale = ttk.Scale(
            vad_frame, from_=0.1, to=0.9, variable=self.vad_threshold,
            orient="horizontal", length=150
        )
        vad_scale.pack(side="left")
        self.vad_label = ttk.Label(vad_frame, text=f"{self.config.audio.vad_threshold:.1f}")
        self.vad_label.pack(side="left", padx=8)
        vad_frame.grid(row=row, column=1, sticky="w", pady=4)
        self.vad_threshold.trace_add("write", lambda *_: self.vad_label.config(
            text=f"{self.vad_threshold.get():.1f}"
        ))
        row += 1

        # ── User Preferences ──
        ttk.Label(main, text="Preferences", style="Header.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(16, 8)
        )
        row += 1

        ttk.Label(main, text="Language Mode:").grid(row=row, column=0, sticky="w", pady=4)
        self.lang_pref = ttk.Combobox(
            main,
            values=["auto", "en", "zh", "en-zh (English-Chinese mixed)",
                    "ja", "en-ja (English-Japanese mixed)",
                    "ko", "en-ko (English-Korean mixed)",
                    "de", "fr", "es"],
            state="readonly", width=28
        )
        # Set current value
        lp = self.config.preferences.language_preference
        for v in self.lang_pref["values"]:
            if v == lp or v.startswith(lp + " ") or v.startswith(lp):
                self.lang_pref.set(v)
                break
        else:
            self.lang_pref.set("auto")
        self.lang_pref.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(main, text="Output Format:").grid(row=row, column=0, sticky="w", pady=4)
        self.output_fmt = ttk.Combobox(
            main, values=["sentences", "natural", "bullet"],
            state="readonly", width=20
        )
        self.output_fmt.set(self.config.preferences.output_format)
        self.output_fmt.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(main, text="Custom Vocabulary:").grid(row=row, column=0, sticky="nw", pady=4)
        vocab_frame = ttk.Frame(main)
        self.vocab_text = tk.Text(
            vocab_frame, width=30, height=3, bg=input_bg, fg=fg,
            font=("Segoe UI", 10), relief="flat", insertbackground=fg,
            wrap="word"
        )
        self.vocab_text.insert("1.0", ", ".join(self.config.preferences.custom_vocabulary))
        self.vocab_text.pack(fill="x")
        ttk.Label(vocab_frame, text="Comma-separated names, terms, acronyms",
                  font=("Segoe UI", 8)).pack(anchor="w")
        vocab_frame.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(main, text="Custom Instructions:").grid(row=row, column=0, sticky="nw", pady=4)
        instr_frame = ttk.Frame(main)
        self.instructions_text = tk.Text(
            instr_frame, width=30, height=2, bg=input_bg, fg=fg,
            font=("Segoe UI", 10), relief="flat", insertbackground=fg,
            wrap="word"
        )
        self.instructions_text.insert("1.0", self.config.preferences.custom_instructions)
        self.instructions_text.pack(fill="x")
        ttk.Label(instr_frame, text='e.g. "Always use formal tone" or "Use British English"',
                  font=("Segoe UI", 8)).pack(anchor="w")
        instr_frame.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        # ── UI Settings ──
        ttk.Label(main, text="Interface", style="Header.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(16, 8)
        )
        row += 1

        self.show_overlay_var = tk.BooleanVar(value=self.config.ui.show_overlay)
        ttk.Checkbutton(main, text="Show floating overlay", variable=self.show_overlay_var).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=4
        )
        row += 1

        self.autostart_var = tk.BooleanVar(value=self._check_autostart())
        ttk.Checkbutton(main, text="Start with Windows", variable=self.autostart_var).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=4
        )
        row += 1

        # ── Buttons ──
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(20, 0))

        save_btn = tk.Button(
            btn_frame, text="  Save  ", font=("Segoe UI", 10, "bold"),
            bg="#89b4fa", fg="#1e1e2e", relief="flat", padx=16, pady=6,
            command=self._save
        )
        save_btn.pack(side="left", padx=8)

        cancel_btn = tk.Button(
            btn_frame, text="  Cancel  ", font=("Segoe UI", 10),
            bg="#45475a", fg="#cdd6f4", relief="flat", padx=16, pady=6,
            command=self._close
        )
        cancel_btn.pack(side="left", padx=8)

        # Center window on screen
        self._root.update_idletasks()
        w = self._root.winfo_width()
        h = self._root.winfo_height()
        x = (self._root.winfo_screenwidth() // 2) - (w // 2)
        y = (self._root.winfo_screenheight() // 2) - (h // 2)
        self._root.geometry(f"+{x}+{y}")

        self._root.mainloop()

    def _save(self):
        """Save settings and close."""
        # Apply to config
        self.config.whisper.model_size = self.whisper_model.get()
        self.config.whisper.device = self.device.get()

        lang_selection = self.language.get()
        if lang_selection == "Auto Detect":
            self.config.whisper.language = None
        else:
            self.config.whisper.language = lang_selection.split(" ")[0]

        self.config.llm.enabled = self.llm_enabled_var.get()
        self.config.llm.model = self.llm_model.get()
        self.config.llm.refinement_level = self.refinement_level.get()

        self.config.audio.vad_threshold = round(self.vad_threshold.get(), 2)
        self.config.ui.show_overlay = self.show_overlay_var.get()

        # User preferences
        lang_sel = self.lang_pref.get().split(" ")[0]  # Strip description
        self.config.preferences.language_preference = lang_sel
        self.config.preferences.output_format = self.output_fmt.get()

        # Parse vocabulary from text area
        vocab_raw = self.vocab_text.get("1.0", "end").strip()
        if vocab_raw:
            self.config.preferences.custom_vocabulary = [
                w.strip() for w in vocab_raw.split(",") if w.strip()
            ]
        else:
            self.config.preferences.custom_vocabulary = []

        self.config.preferences.custom_instructions = self.instructions_text.get("1.0", "end").strip()

        # Save to disk
        self.config.save()
        logger.info("Settings saved")

        # Handle autostart
        if self.autostart_var.get():
            self._enable_autostart()
        else:
            self._disable_autostart()

        if self.on_save:
            self.on_save(self.config)

        self._close()

    def _close(self):
        if self._root:
            self._root.destroy()
            self._root = None

    # ── Windows Auto-Start ──

    def _check_autostart(self) -> bool:
        """Check if Voice IME is set to start with Windows."""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ
            )
            try:
                winreg.QueryValueEx(key, "VoiceIME")
                return True
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except Exception:
            return False

    def _enable_autostart(self):
        """Add Voice IME to Windows startup."""
        try:
            import winreg
            import sys
            import os

            # Use the exe path if packaged, otherwise python + script
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = f'"{sys.executable}" "{os.path.abspath("main.py")}"'

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, "VoiceIME", 0, winreg.REG_SZ, exe_path)
            winreg.CloseKey(key)
            logger.info(f"Auto-start enabled: {exe_path}")
        except Exception as e:
            logger.error(f"Failed to enable auto-start: {e}")

    def _disable_autostart(self):
        """Remove Voice IME from Windows startup."""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            try:
                winreg.DeleteValue(key, "VoiceIME")
                logger.info("Auto-start disabled")
            except FileNotFoundError:
                pass
            finally:
                winreg.CloseKey(key)
        except Exception as e:
            logger.error(f"Failed to disable auto-start: {e}")
