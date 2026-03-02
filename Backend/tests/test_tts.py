import os
import wave
from pathlib import Path
from tools.speech import _synthesize_speech_sync

ZH_TEXT = "你好，这是一段中文语音合成测试。"
EN_TEXT = "Hello, this is an English text-to-speech test."

OUT_DIR = Path(__file__).parent


def run_test(text: str, lang: str, out_filename: str) -> int:
    print(f"Synthesizing [{lang}]: {text!r}")
    wav_bytes = _synthesize_speech_sync(text, lang=lang)
    out_path = OUT_DIR / out_filename
    with open(out_path, "wb") as f:
        f.write(wav_bytes)
    print(f"Wrote {len(wav_bytes)} bytes to {out_path}")

    with wave.open(str(out_path), "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        duration = n_frames / framerate
    print(f"  WAV: {channels}ch, {sample_width*8}bit, {framerate}Hz, {duration:.2f}s")
    return len(wav_bytes)


def main():
    print("=== Piper TTS test ===")
    print(f"ZH model: {os.getenv('PIPER_ZH_MODEL', 'default')}")
    print(f"EN model: {os.getenv('PIPER_EN_MODEL', 'default')}")

    run_test(ZH_TEXT, "zh", "piper_test_zh.wav")
    run_test(EN_TEXT, "en", "piper_test_en.wav")
    print("Done.")


main()
