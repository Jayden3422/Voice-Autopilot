import os
import re
import tempfile

import edge_tts
from edge_tts.exceptions import NoAudioReceived, UnexpectedResponse, WebSocketError
from faster_whisper import WhisperModel
from opencc import OpenCC

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


# TTS
VOICE_NAME = "zh-CN-XiaoxiaoNeural"
VOICE_BY_LANG = {
  "zh": "zh-CN-XiaoxiaoNeural",
  "en": "en-US-JennyNeural",
}
VOICE_FALLBACKS = {
  "zh": ["zh-CN-XiaoxiaoNeural", "zh-CN-XiaoyiNeural", "zh-CN-YunxiNeural"],
  "en": ["en-US-JennyNeural", "en-US-GuyNeural", "en-CA-ClaraNeural"],
}

PROXY = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
CONNECT_TIMEOUT = int(os.getenv("EDGE_TTS_CONNECT_TIMEOUT", "10"))
RECEIVE_TIMEOUT = int(os.getenv("EDGE_TTS_RECEIVE_TIMEOUT", "60"))

TTS_SEGMENT_MAX_CHARS = int(os.getenv("TTS_SEGMENT_MAX_CHARS", "48"))
TTS_FIRST_SEGMENT_CHARS = int(os.getenv("TTS_FIRST_SEGMENT_CHARS", "16"))
TTS_MIN_PUNCT_BREAK_CHARS = int(os.getenv("TTS_MIN_PUNCT_BREAK_CHARS", "8"))
_TTS_BREAK_PUNCT = set("?!?!?;;,,?.")


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


async def synthesize_speech(text: str, lang: str = "zh") -> bytes:
  normalized = _normalize_lang(lang)
  primary_voice = VOICE_BY_LANG.get(normalized, VOICE_NAME)
  voices = [primary_voice] + [v for v in VOICE_FALLBACKS.get(normalized, []) if v != primary_voice]
  last_error = None

  for voice in voices:
    try:
      communicate = edge_tts.Communicate(
        text,
        voice,
        proxy=PROXY,
        connect_timeout=CONNECT_TIMEOUT,
        receive_timeout=RECEIVE_TIMEOUT,
      )
      audio_bytes = bytearray()
      async for chunk in communicate.stream():
        if chunk["type"] == "audio":
          audio_bytes.extend(chunk["data"])
      if audio_bytes:
        return bytes(audio_bytes)
      last_error = NoAudioReceived("No audio was received.")
    except (NoAudioReceived, WebSocketError, UnexpectedResponse) as e:
      last_error = e
    except Exception as e:
      last_error = e

  if last_error:
    raise last_error
  raise NoAudioReceived("No audio was received.")

