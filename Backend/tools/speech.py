import asyncio
import io
import os
import re
import tempfile
import threading
import wave
from pathlib import Path

from faster_whisper import WhisperModel
from opencc import OpenCC
from piper import PiperVoice

cc = OpenCC("t2s")

# STT
_model = WhisperModel(
  "small",
  device="cpu",
  compute_type="int8",
)

STT_BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "1"))
STT_BEST_OF = int(os.getenv("WHISPER_BEST_OF", "1"))
STT_VAD_FILTER = os.getenv("WHISPER_VAD_FILTER", "true").lower() not in {"0", "false", "no"}
STT_NO_SPEECH_THRESHOLD = float(os.getenv("WHISPER_NO_SPEECH_THRESHOLD", "0.5"))


def _normalize_lang(lang: str) -> str:
  if not lang:
    return "zh"
  lang = lang.lower()
  return "en" if lang.startswith("en") else "zh"


def transcribe_audio(path: str, lang: str = "zh") -> str:
  normalized = _normalize_lang(lang)
  segments, _ = _model.transcribe(
    path,
    language=normalized,
    beam_size=STT_BEAM_SIZE,
    best_of=STT_BEST_OF,
    vad_filter=STT_VAD_FILTER,
    no_speech_threshold=STT_NO_SPEECH_THRESHOLD,
  )
  text = "".join(seg.text for seg in segments)
  if normalized == "zh":
    text = cc.convert(text)
  return text.strip()


def transcribe_audio_bytes(audio_bytes: bytes, lang: str = "zh", suffix: str = ".webm") -> str:
  with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
    f.write(audio_bytes)
    tmp_path = f.name
  try:
    return transcribe_audio(tmp_path, lang=lang)
  finally:
    try:
      os.remove(tmp_path)
    except Exception:
      pass


def common_prefix_length(left: str, right: str) -> int:
  limit = min(len(left), len(right))
  idx = 0
  while idx < limit and left[idx] == right[idx]:
    idx += 1
  return idx


def delta_from_previous(previous: str, current: str) -> str:
  if not current:
    return ""
  if not previous:
    return current
  return current[common_prefix_length(previous, current):]


# TTS - Piper (local, offline)
_MODELS_DIR = Path(os.getenv(
  "PIPER_MODELS_DIR",
  str(Path(__file__).resolve().parent.parent / "models" / "piper"),
))

PIPER_ZH_MODEL = os.getenv("PIPER_ZH_MODEL", str(_MODELS_DIR / "zh_CN-xiao_ya-medium.onnx"))
PIPER_EN_MODEL = os.getenv("PIPER_EN_MODEL", str(_MODELS_DIR / "en_US-amy-medium.onnx"))

_PIPER_MODEL_BY_LANG = {
  "zh": PIPER_ZH_MODEL,
  "en": PIPER_EN_MODEL,
}

TTS_SEGMENT_MAX_CHARS = int(os.getenv("TTS_SEGMENT_MAX_CHARS", "48"))
TTS_FIRST_SEGMENT_CHARS = int(os.getenv("TTS_FIRST_SEGMENT_CHARS", "16"))
TTS_MIN_PUNCT_BREAK_CHARS = int(os.getenv("TTS_MIN_PUNCT_BREAK_CHARS", "8"))
_TTS_BREAK_PUNCT = set("?!?!?;;,,?.")

_piper_voices: dict[str, PiperVoice] = {}
_piper_lock = threading.Lock()


def _get_piper_voice(lang: str) -> PiperVoice:
  normalized = _normalize_lang(lang)
  if normalized in _piper_voices:
    return _piper_voices[normalized]
  with _piper_lock:
    if normalized in _piper_voices:
      return _piper_voices[normalized]
    model_path = _PIPER_MODEL_BY_LANG.get(normalized, PIPER_ZH_MODEL)
    voice = PiperVoice.load(model_path, use_cuda=False)
    _piper_voices[normalized] = voice
    return voice


def _normalize_tts_text(text: str) -> str:
  normalized = (text or "").strip()
  normalized = re.sub(r"\s+", " ", normalized)
  return normalized


def segment_tts_text(
  text: str,
  max_chars: int = TTS_SEGMENT_MAX_CHARS,
  first_segment_chars: int = TTS_FIRST_SEGMENT_CHARS,
) -> list[str]:
  normalized = _normalize_tts_text(text)
  if not normalized:
    return []

  first_target = max(8, first_segment_chars)
  regular_target = max(12, max_chars)
  min_punct_break = max(4, TTS_MIN_PUNCT_BREAK_CHARS)

  segments: list[str] = []
  buff: list[str] = []
  target = first_target
  for ch in normalized:
    buff.append(ch)
    current = "".join(buff).strip()
    if not current:
      continue
    by_punct = ch in _TTS_BREAK_PUNCT and len(current) >= min_punct_break
    by_length = len(current) >= target
    if by_punct or by_length:
      segments.append(current)
      buff = []
      target = regular_target

  tail = "".join(buff).strip()
  if tail:
    segments.append(tail)
  return [seg for seg in segments if seg]


def _synthesize_speech_sync(text: str, lang: str = "zh") -> bytes:
  normalized = _normalize_lang(lang)
  voice = _get_piper_voice(normalized)
  chunks = list(voice.synthesize(text))
  if not chunks:
    raise RuntimeError("Piper produced no audio chunks")
  first = chunks[0]
  buf = io.BytesIO()
  with wave.open(buf, "wb") as wav_file:
    wav_file.setnchannels(first.sample_channels)
    wav_file.setsampwidth(first.sample_width)
    wav_file.setframerate(first.sample_rate)
    for chunk in chunks:
      wav_file.writeframes(chunk.audio_int16_bytes)
  return buf.getvalue()


async def synthesize_speech(text: str, lang: str = "zh") -> bytes:
  return await asyncio.to_thread(_synthesize_speech_sync, text, lang)
