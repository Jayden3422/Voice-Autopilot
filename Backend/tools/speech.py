from faster_whisper import WhisperModel
import edge_tts
import asyncio
import os
from opencc import OpenCC
cc = OpenCC('t2s') # 繁体转简体

# STT
_model = WhisperModel(
  "small",
  device="cpu",
  compute_type="int8"
)

def transcribe_audio(path: str) -> str:
  # 音频转文本
  segments, _ = _model.transcribe(path, language="zh")
  text = "".join(seg.text for seg in segments)
  text = cc.convert(text)  # 繁体转简体
  return text.strip()

# TTS
VOICE_NAME = "zh-CN-XiaoxiaoNeural"

async def synthesize_speech(text: str) -> bytes:
  # 语音（二进制 wav）
  communicate = edge_tts.Communicate(text, VOICE_NAME)
  audio_bytes = b""
  async for chunk in communicate.stream():
    if chunk["type"] == "audio":
      audio_bytes += chunk["data"]
  return audio_bytes


if __name__ == "__main__":
  # 测试语音识别
  base_dir = os.path.dirname(__file__)
  wav_path = os.path.join(base_dir, "../../Frontend/src/assets/audio/welcome.wav")
  wav_path = os.path.normpath(wav_path)
  print("STT ...")
  text = transcribe_audio(wav_path)
  print(text)

  # 测试语音合成
  async def test_tts():
    text = "您好，我是您的日程助手，你要记录什么日程？"
    print("TTS ...")
    audio_bytes = await synthesize_speech(text)
    output = "test_tts.wav"
    with open(output, "wb") as f:
        f.write(audio_bytes)
    print(f"TTS：{output}")
  
  asyncio.run(test_tts())