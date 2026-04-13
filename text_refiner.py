"""
Voice IME — Text Refinement Module
Uses a local LLM (Gemma 4 via Ollama) to polish raw speech-to-text output.
"""

import logging
import json
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger("voice-ime.refiner")


class TextRefiner:
    """
    Sends raw transcript to a local Ollama server for text refinement
    (grammar, punctuation, formatting fixes).
    """

    def __init__(self, config):
        """
        Args:
            config: AppConfig instance
        """
        self.config = config
        self._available = None  # None = unchecked, True/False = checked

    def check_availability(self) -> bool:
        """Check if the Ollama server is running and the model is available."""
        try:
            url = f"{self.config.llm.ollama_base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                
                # Check if our target model is available
                target = self.config.llm.model
                # Ollama model names can have :latest suffix
                found = any(
                    target in m or m.startswith(target.split(":")[0])
                    for m in models
                )
                
                if found:
                    logger.info(f"Ollama is running, model '{target}' is available")
                    self._available = True
                else:
                    logger.warning(
                        f"Ollama is running but model '{target}' not found. "
                        f"Available: {models}. Run: ollama pull {target}"
                    )
                    self._available = False
                return self._available
                
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            self._available = False
            return False

    def refine(self, raw_text: str) -> str:
        """
        Refine raw transcript text using the local LLM.
        
        Args:
            raw_text: Raw speech-to-text output
            
        Returns:
            Refined text, or the original text if refinement fails/is disabled
        """
        lc = self.config.llm
        
        # Skip if disabled
        if not lc.enabled or lc.refinement_level == "off":
            logger.info("Text refinement is disabled, returning raw text")
            return raw_text
        
        # Skip empty text
        if not raw_text or not raw_text.strip():
            return raw_text
        
        # Check availability on first call
        if self._available is None:
            self.check_availability()
        
        if not self._available:
            logger.warning("Ollama not available, returning raw text")
            return raw_text
        
        # Select system prompt based on refinement level
        if lc.refinement_level == "full":
            base_prompt = lc.system_prompt_full
        else:
            base_prompt = lc.system_prompt_light
        
        # Build enhanced prompt with user preferences
        system_prompt = self._build_system_prompt(base_prompt)
        
        try:
            result = self._call_ollama(system_prompt, raw_text)
            if result and result.strip():
                logger.info(f"Text refined: {len(raw_text)} -> {len(result)} chars")
                return result.strip()
            else:
                logger.warning("Empty refinement result, returning raw text")
                return raw_text
                
        except Exception as e:
            logger.error(f"Text refinement failed: {e}")
            return raw_text

    def _call_ollama(self, system_prompt: str, user_text: str) -> str:
        """Make a request to the Ollama API."""
        lc = self.config.llm
        
        payload = {
            "model": lc.model,
            "prompt": user_text,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,       # Low temperature for precise corrections
                "top_p": 0.9,
                "num_predict": len(user_text) * 3,  # Allow up to 3x input length
            }
        }
        
        url = f"{lc.ollama_base_url}/api/generate"
        data = json.dumps(payload).encode("utf-8")
        
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        logger.debug(f"Calling Ollama: model={lc.model}, text_len={len(user_text)}")
        
        with urllib.request.urlopen(req, timeout=lc.timeout_seconds) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            response_text = result.get("response", "")
            
            # Log timing info
            total_duration = result.get("total_duration", 0) / 1e9  # ns to seconds
            logger.debug(f"Ollama response in {total_duration:.1f}s")
            
            return response_text

    @property
    def is_available(self) -> Optional[bool]:
        """Whether Ollama is available. None if unchecked."""
        return self._available

    def _build_system_prompt(self, base_prompt: str) -> str:
        """
        Build an enhanced system prompt incorporating user preferences.
        Adds custom vocabulary, language instructions, and formatting rules.
        """
        prefs = self.config.preferences
        parts = [base_prompt]

        # Language preference
        lang = prefs.language_preference
        if lang == "en-zh":
            parts.append(
                "IMPORTANT: The text may contain a mix of English and Chinese (code-switching). "
                "Preserve both languages naturally. Do not translate between them. "
                "Apply correct punctuation for each language (periods for English, "
                "。for Chinese sentences)."
            )
        elif lang == "en-ja":
            parts.append(
                "IMPORTANT: The text may contain a mix of English and Japanese. "
                "Preserve both languages naturally. Do not translate between them."
            )
        elif lang == "zh":
            parts.append("The text is in Chinese. Use Chinese punctuation (，。！？).")
        elif lang == "ja":
            parts.append("The text is in Japanese. Use appropriate Japanese punctuation.")
        elif lang == "en":
            parts.append("The text is in English.")

        # Custom vocabulary
        if prefs.custom_vocabulary:
            vocab_str = ", ".join(prefs.custom_vocabulary)
            parts.append(
                f"IMPORTANT: The following are known proper nouns, names, or technical terms "
                f"that must be preserved exactly as listed: {vocab_str}. "
                f"If the speech-to-text produced a similar-sounding but incorrect word, "
                f"correct it to the proper term from this list."
            )

        # Output format
        fmt = prefs.output_format
        if fmt == "sentences":
            parts.append("Add proper sentence-ending punctuation.")
        elif fmt == "bullet":
            parts.append("Format the output as bullet points, one per idea.")
        elif fmt == "natural":
            parts.append("Keep the natural speaking flow without adding extra punctuation.")

        # Custom instructions from user
        if prefs.custom_instructions:
            parts.append(f"Additional instructions: {prefs.custom_instructions}")

        return "\n\n".join(parts)

