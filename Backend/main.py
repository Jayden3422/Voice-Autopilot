import base64
import os
from datetime import datetime

import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from tools.models import VoiceResponse
from tools.file_utils import save_temp_file
from tools.speech import transcribe_audio, synthesize_speech
from tools.nlp import parse_calendar_command

app = FastAPI(title="Voice Schedule Assistant")

app.add_middleware(
  CORSMiddleware,
  allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

@app.post("/voice", response_model=VoiceResponse)
async def handle_voice(audio: UploadFile = File(...)):
  if not audio:
    raise HTTPException(status_code=400, detail="未收到音频文件")

  temp_path = save_temp_file(audio)

  try:
    # STT
    user_text = transcribe_audio(temp_path)
    if not user_text.strip():
      ai_text = "我没有听清你说的话，可以再说一遍吗？"
      audio_bytes = await synthesize_speech(ai_text)
      audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
      return VoiceResponse(
        user_text="（识别失败）",
        ai_text=ai_text,
        audio_base64=audio_b64,
      )

    # NLP
    now = datetime.now()
    try:
      cmd = parse_calendar_command(user_text, now=now)
    except Exception as e:
      print("NLP 解析失败：", e)
      ai_text = "我没完全听懂你的时间或标题，可以再更清楚地说一次吗？例如：明天上午十点到十一点和公司 CEO 会议。"
      audio_bytes = await synthesize_speech(ai_text)
      audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
      return VoiceResponse(
        user_text=user_text,
        ai_text=ai_text,
        audio_base64=audio_b64,
      )
    
    ai_text = f"{cmd.date} 从 {cmd.start_time} 到 {cmd.end_time}：{cmd.title}"

    # TTS
    audio_bytes = await synthesize_speech(ai_text)
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    return VoiceResponse(
      user_text=user_text,
      ai_text=ai_text,
      audio_base64=audio_b64,
    )

  except HTTPException:
    raise
  except Exception as e:
    print("处理语音时异常：", e)
    raise HTTPException(status_code=500, detail="服务器处理语音失败")
  finally:
    try:
      os.remove(temp_path)
    except Exception:
      pass

if __name__ == "__main__":
  uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
