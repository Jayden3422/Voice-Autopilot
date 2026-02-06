import asyncio
import os
import edge_tts
from edge_tts.exceptions import NoAudioReceived, WebSocketError, UnexpectedResponse

TEXT = "Hello from edge tts test"
VOICES = [
    "en-US-JennyNeural",
    "en-US-GuyNeural",
    "en-CA-ClaraNeural",
]

PROXY = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
CONNECT_TIMEOUT = int(os.getenv("EDGE_TTS_CONNECT_TIMEOUT", "10"))
RECEIVE_TIMEOUT = int(os.getenv("EDGE_TTS_RECEIVE_TIMEOUT", "60"))

async def run_once(voice: str, out_path: str) -> int:
    print(f"Using voice: {voice}")
    communicate = edge_tts.Communicate(
        TEXT,
        voice,
        proxy=PROXY,
        connect_timeout=CONNECT_TIMEOUT,
        receive_timeout=RECEIVE_TIMEOUT,
    )
    bytes_written = 0
    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
                bytes_written += len(chunk["data"])
    return bytes_written

async def main():
    print(f"edge_tts version: {getattr(edge_tts, '__version__', 'unknown')}")
    print(f"Proxy: {PROXY or 'none'}")
    out_path = os.path.join(os.path.dirname(__file__), "edge_tts_test.mp3")

    last_error = None
    for voice in VOICES:
        try:
            bytes_written = await run_once(voice, out_path)
            print(f"Wrote {bytes_written} bytes to {out_path}")
            if bytes_written > 0:
                return
        except (NoAudioReceived, WebSocketError, UnexpectedResponse) as e:
            last_error = e
            print(f"TTS failed for {voice}: {e}")
        except Exception as e:
            last_error = e
            print(f"Unexpected error for {voice}: {e}")

    if last_error:
        raise last_error

asyncio.run(main())