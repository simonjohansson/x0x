"""Strict mono integer-PCM WAV input/output with no implicit normalization."""
import math
import wave
from pathlib import Path


def read_wav(path):
    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getcomptype() != "NONE" or wav.getsampwidth() not in (2, 3, 4):
            raise ValueError("expected mono 16/24/32-bit integer PCM WAV")
        width, count, rate = wav.getsampwidth(), wav.getnframes(), wav.getframerate()
        raw = wav.readframes(count + 1)
    if count == 0 or len(raw) != count * width:
        raise ValueError("empty or truncated PCM data")
    return [int.from_bytes(raw[i:i + width], "little", signed=True) / 2 ** (8 * width - 1)
            for i in range(0, len(raw), width)], rate


def write_wav(path, samples, sample_rate):
    if not samples or not all(type(x) in (int, float) and math.isfinite(x) and -1 <= x <= 1 for x in samples):
        raise ValueError("PCM output requires finite samples in -1..1; no automatic clipping")
    if type(sample_rate) is not int or not 8000 <= sample_rate <= 192000:
        raise ValueError("invalid PCM sample rate")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = b"".join(max(-32768, min(32767, round(x * 32768))).to_bytes(2, "little", signed=True) for x in samples)
    with wave.open(str(path), "wb") as wav:
        wav.setparams((1, 2, sample_rate, 0, "NONE", "not compressed"))
        wav.writeframes(raw)
