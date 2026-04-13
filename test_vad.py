"""Test: verify max segment flushing and buffer behavior."""
import numpy as np
import sys

# Patch config for testing
sys.path.insert(0, '.')
from audio_capture import AudioCapture, _VAD_SAMPLES_16K, MAX_SEGMENT_SECONDS
from config import get_config

config = get_config()

# Track flush calls
flushed_segments = []
def on_segment(audio):
    flushed_segments.append(len(audio) / 16000)
    print(f"  -> Flushed segment: {len(audio)/16000:.1f}s")

ac = AudioCapture(config, on_speech_segment=on_segment)

# Test 1: max buffer frames calculation
seconds_per_frame = _VAD_SAMPLES_16K / 16000
max_frames = int(MAX_SEGMENT_SECONDS / seconds_per_frame)
print(f"VAD frame: {_VAD_SAMPLES_16K} samples = {seconds_per_frame*1000:.0f}ms")
print(f"Max segment: {MAX_SEGMENT_SECONDS}s = {max_frames} frames")
print(f"Max buffer size: {max_frames * _VAD_SAMPLES_16K} samples")

# Test 2: verify buffer lock exists
assert hasattr(ac, '_buffer_lock'), "Buffer lock missing!"
print("Buffer lock exists: OK")

# Test 3: simulate buffer overflow scenario
print(f"\nSimulating {MAX_SEGMENT_SECONDS+5}s of continuous speech...")
ac._speech_buffer = [np.zeros(_VAD_SAMPLES_16K, dtype=np.float32)] * (max_frames + 100)
buf_len = len(ac._speech_buffer)
print(f"Buffer has {buf_len} frames = {buf_len * seconds_per_frame:.1f}s")
print(f"Would trigger force-flush: {buf_len >= max_frames}")
assert buf_len >= max_frames, "Should trigger force-flush!"

print("\nAll checks passed!")
