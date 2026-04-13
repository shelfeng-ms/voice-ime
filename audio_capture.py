"""
Voice IME — Audio Capture Module
Handles microphone streaming with Silero VAD for voice activity detection.
"""

import threading
import queue
import time
import logging
import numpy as np

logger = logging.getLogger("voice-ime.audio")

# Silero VAD requires EXACTLY these sample counts
_VAD_SAMPLES_16K = 512   # for 16000 Hz
_VAD_SAMPLES_8K = 256    # for 8000 Hz

# Maximum duration (seconds) before force-flushing a speech segment.
# Prevents unbounded buffering during long continuous speech.
MAX_SEGMENT_SECONDS = 15


class AudioCapture:
    """
    Captures audio from the microphone and uses Silero VAD to detect speech.
    
    When speech is detected, audio is buffered. The buffer is flushed when:
      1. Silence exceeds the grace period (natural sentence boundary), OR
      2. The buffer exceeds MAX_SEGMENT_SECONDS (prevents unbounded growth), OR
      3. The user manually stops recording.
    """

    def __init__(self, config, on_speech_segment):
        """
        Args:
            config: AppConfig instance
            on_speech_segment: Callback function(np.ndarray) called with complete speech audio
        """
        self.config = config
        self.on_speech_segment = on_speech_segment
        
        self._is_recording = False
        self._stream = None
        self._thread = None
        self._stop_event = threading.Event()
        
        # Audio buffer for current speech segment
        self._speech_buffer = []
        self._buffer_lock = threading.Lock()
        self._silence_start = None
        self._is_speaking = False
        
        # VAD model (lazy loaded)
        self._vad_model = None
        self._vad_ready = False

        # Status callback for UI updates
        self.on_status_change = None

    def _load_vad(self):
        """Load Silero VAD model."""
        if self._vad_ready:
            return
        try:
            import torch
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False,
                trust_repo=True
            )
            self._vad_model = model
            self._vad_ready = True
            logger.info("Silero VAD loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Silero VAD: {e}")
            raise

    def _get_vad_confidence(self, audio_chunk: np.ndarray) -> float:
        """Run VAD on an audio chunk and return speech probability."""
        import torch
        if not self._vad_ready:
            return 0.0
        
        # Convert to torch tensor
        tensor = torch.from_numpy(audio_chunk).float()
        
        # Run VAD
        speech_prob = self._vad_model(tensor, self.config.audio.sample_rate).item()
        return speech_prob

    def start(self):
        """Start capturing audio from the microphone."""
        if self._is_recording:
            logger.warning("Already recording")
            return
        
        logger.info("Starting audio capture...")
        self._load_vad()
        
        self._is_recording = True
        self._stop_event.clear()
        with self._buffer_lock:
            self._speech_buffer = []
        self._silence_start = None
        self._is_speaking = False
        
        # Reset VAD state
        if self._vad_model is not None:
            self._vad_model.reset_states()
        
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        
        self._notify_status("listening")
        logger.info("Audio capture started")

    def stop(self):
        """Stop capturing audio. If speech was buffered, process it."""
        if not self._is_recording:
            return
        
        logger.info("Stopping audio capture...")
        self._is_recording = False
        self._stop_event.set()
        
        # Wait for capture thread to finish so the buffer is final
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        
        # Now flush any remaining speech buffer
        with self._buffer_lock:
            if self._speech_buffer:
                buf_duration = len(self._speech_buffer) * (_VAD_SAMPLES_16K / self.config.audio.sample_rate)
                logger.info(f"Flushing remaining buffer on stop: {buf_duration:.1f}s")
                self._flush_speech_buffer()
        
        self._notify_status("idle")
        logger.info("Audio capture stopped")

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def _capture_loop(self):
        """Main capture loop running in a background thread."""
        import sounddevice as sd
        
        sample_rate = self.config.audio.sample_rate
        silence_grace = self.config.audio.silence_grace_ms / 1000.0
        min_speech = self.config.audio.min_speech_duration_ms / 1000.0
        vad_threshold = self.config.audio.vad_threshold
        
        # Silero VAD frame size — MUST be exactly 512 at 16kHz or 256 at 8kHz
        vad_frame = _VAD_SAMPLES_16K if sample_rate == 16000 else _VAD_SAMPLES_8K
        seconds_per_frame = vad_frame / sample_rate
        max_buffer_frames = int(MAX_SEGMENT_SECONDS / seconds_per_frame)
        
        try:
            with sd.InputStream(
                samplerate=sample_rate,
                channels=self.config.audio.channels,
                dtype='float32',
                blocksize=vad_frame
            ) as stream:
                logger.info(
                    f"Mic stream opened: {sample_rate}Hz, "
                    f"vad_frame={vad_frame}, max_segment={MAX_SEGMENT_SECONDS}s"
                )
                
                while not self._stop_event.is_set():
                    # Read exactly one VAD frame
                    audio_data, overflowed = stream.read(vad_frame)
                    if overflowed:
                        logger.warning("Audio buffer overflowed")
                    
                    # Flatten to 1D
                    chunk = audio_data[:, 0] if audio_data.ndim > 1 else audio_data.flatten()
                    
                    # Safety: ensure exact frame size for VAD
                    if len(chunk) != vad_frame:
                        if len(chunk) < vad_frame:
                            chunk = np.pad(chunk, (0, vad_frame - len(chunk)))
                        else:
                            chunk = chunk[:vad_frame]
                    
                    # Run VAD
                    speech_prob = self._get_vad_confidence(chunk)
                    
                    if speech_prob >= vad_threshold:
                        # ── Speech detected ──
                        if not self._is_speaking:
                            self._is_speaking = True
                            logger.debug("Speech started")
                        
                        with self._buffer_lock:
                            self._speech_buffer.append(chunk.copy())
                            buf_len = len(self._speech_buffer)
                        self._silence_start = None
                        
                        # Force-flush if buffer exceeds max duration
                        if buf_len >= max_buffer_frames:
                            duration = buf_len * seconds_per_frame
                            logger.info(f"Max segment reached ({duration:.1f}s), force-flushing")
                            with self._buffer_lock:
                                self._flush_speech_buffer()
                            # Keep speaking state — next frames continue into a new buffer
                        
                    else:
                        # ── Silence detected ──
                        if self._is_speaking:
                            # Append silence frames during grace period (avoid cutting words)
                            with self._buffer_lock:
                                self._speech_buffer.append(chunk.copy())
                            
                            if self._silence_start is None:
                                self._silence_start = time.time()
                            
                            elapsed_silence = time.time() - self._silence_start
                            
                            if elapsed_silence >= silence_grace:
                                # Grace period exceeded — flush buffer
                                with self._buffer_lock:
                                    total_duration = len(self._speech_buffer) * seconds_per_frame
                                    
                                    if total_duration >= min_speech:
                                        logger.info(f"Speech segment: {total_duration:.1f}s")
                                        self._flush_speech_buffer()
                                    else:
                                        logger.debug(f"Ignoring short segment: {total_duration:.2f}s")
                                        self._speech_buffer = []
                                
                                self._is_speaking = False
                                self._silence_start = None
                
        except Exception as e:
            logger.error(f"Audio capture error: {e}")
            self._notify_status("error")
        finally:
            self._is_recording = False

    def _flush_speech_buffer(self):
        """
        Concatenate buffered speech and send to callback.
        Caller MUST hold self._buffer_lock.
        """
        if not self._speech_buffer:
            return
        
        audio = np.concatenate(self._speech_buffer)
        self._speech_buffer = []
        
        # Reset VAD state for next segment
        if self._vad_model is not None:
            self._vad_model.reset_states()
        
        self._notify_status("processing")
        
        # Call the processing callback in a separate thread to not block capture
        threading.Thread(
            target=self.on_speech_segment,
            args=(audio,),
            daemon=True
        ).start()

    def _notify_status(self, status: str):
        """Notify UI about status changes."""
        if self.on_status_change:
            try:
                self.on_status_change(status)
            except Exception as e:
                logger.error(f"Status callback error: {e}")
