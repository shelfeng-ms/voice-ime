"""
Voice IME — Speech-to-Text Module
Wraps faster-whisper for local speech recognition.
"""

import logging
import numpy as np
from typing import Optional

logger = logging.getLogger("voice-ime.stt")


class SpeechToText:
    """
    Transcribes audio using faster-whisper.
    Supports GPU (CUDA) and CPU inference with configurable model sizes.
    """

    def __init__(self, config):
        """
        Args:
            config: AppConfig instance
        """
        self.config = config
        self._model = None
        self._loaded = False

    def load_model(self):
        """Load the Whisper model. Call this during startup."""
        if self._loaded:
            return
        
        from faster_whisper import WhisperModel
        
        wc = self.config.whisper
        
        # Determine device and compute type
        device = wc.device
        compute_type = wc.compute_type
        
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        
        if compute_type == "auto":
            compute_type = "float16" if device == "cuda" else "int8"
        
        logger.info(f"Loading Whisper model: {wc.model_size} on {device} ({compute_type})")
        
        self._model = WhisperModel(
            wc.model_size,
            device=device,
            compute_type=compute_type,
        )
        self._loaded = True
        logger.info("Whisper model loaded successfully")

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe audio to text.
        
        Args:
            audio: numpy array of float32 audio samples at 16kHz
            
        Returns:
            Transcribed text string
        """
        if not self._loaded:
            self.load_model()
        
        wc = self.config.whisper
        prefs = self.config.preferences
        
        logger.info(f"Transcribing {len(audio) / 16000:.1f}s of audio...")
        
        # Build initial_prompt from user preferences.
        # Whisper uses this to bias recognition toward these words/patterns.
        initial_prompt = self._build_initial_prompt(prefs)
        
        # Determine language override from preferences
        language = wc.language
        if language is None and prefs.language_preference != "auto":
            # For mixed languages like "en-zh", use the primary language
            # Whisper handles code-switching reasonably if given the right prompt
            lang_code = prefs.language_preference.split("-")[0]
            if lang_code in ("en", "zh", "ja", "ko", "de", "fr", "es", "it", "pt", "ru"):
                language = lang_code
        
        segments, info = self._model.transcribe(
            audio,
            beam_size=wc.beam_size,
            language=language,
            task=wc.task,
            initial_prompt=initial_prompt if initial_prompt else None,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
            ),
        )
        
        # Collect all segment texts
        texts = []
        for segment in segments:
            logger.debug(f"  [{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
            texts.append(segment.text.strip())
        
        result = " ".join(texts).strip()
        
        lang = info.language if info.language else "unknown"
        prob = info.language_probability if info.language_probability else 0
        logger.info(f"Transcription complete: lang={lang} ({prob:.0%}), length={len(result)} chars")
        
        return result

    def _build_initial_prompt(self, prefs) -> str:
        """
        Build Whisper's initial_prompt from user preferences.
        
        The initial_prompt biases Whisper's decoder toward specific words,
        names, and patterns. This is the official way to add custom vocabulary.
        """
        parts = []
        
        # Add language context hint for mixed-language speech
        lang_pref = prefs.language_preference
        if lang_pref == "en-zh":
            parts.append("This is a mixed English and Chinese conversation. 这是中英文混合的对话。")
        elif lang_pref == "en-ja":
            parts.append("This is a mixed English and Japanese conversation. これは英語と日本語の会話です。")
        elif lang_pref == "en-ko":
            parts.append("This is a mixed English and Korean conversation.")
        elif lang_pref == "zh":
            parts.append("这是中文语音输入。")
        elif lang_pref == "ja":
            parts.append("これは日本語の音声入力です。")
        
        # Add custom vocabulary words
        # Whisper uses these as context to bias recognition
        if prefs.custom_vocabulary:
            vocab_str = ", ".join(prefs.custom_vocabulary)
            parts.append(f"Key terms: {vocab_str}.")
        
        return " ".join(parts) if parts else ""

    def is_loaded(self) -> bool:
        return self._loaded
