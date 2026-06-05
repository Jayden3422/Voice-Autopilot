from typing import Optional

from pydantic import BaseModel


class VoiceResponse(BaseModel):
  # /api/voice
  user_text: str
  ai_text: str
  audio_base64: str  # 回复语音
  session_id: str | None = None


class AutopilotRunRequest(BaseModel):
  mode: str  # "audio" or "text"
  audio_base64: Optional[str] = None
  text: Optional[str] = None
  locale: Optional[str] = "en"


class AutopilotConfirmRequest(BaseModel):
  run_id: str
  actions: list[dict]


class AutopilotAdjustRequest(BaseModel):
  mode: str  # "audio" or "text"
  text: Optional[str] = None
  audio_base64: Optional[str] = None
  locale: Optional[str] = "en"
  action: dict
