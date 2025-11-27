class VoiceResponse(BaseModel):
  # /api/voice
  user_text: str
  ai_text: str
  audio_base64: str  # 回复语音
