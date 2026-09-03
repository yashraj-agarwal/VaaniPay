import base64
import os
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()
SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"

LANG_TTS_CONFIG = {
    "hi": {"target_language_code": "hi-IN", "speaker": "anushka"},
    "en": {"target_language_code": "en-IN", "speaker": "vidya"},
    "ta": {"target_language_code": "ta-IN", "speaker": "manisha"},
    "te": {"target_language_code": "te-IN", "speaker": "anushka"},
    "kn": {"target_language_code": "kn-IN", "speaker": "manisha"},
    "ml": {"target_language_code": "ml-IN", "speaker": "arya"},
    "mr": {"target_language_code": "mr-IN", "speaker": "manisha"},
    "bn": {"target_language_code": "bn-IN", "speaker": "anushka"},
    "gu": {"target_language_code": "gu-IN", "speaker": "vidya"},
}

def generate_tts(text: str, lang_key: str) -> bytes:
    api_key = os.getenv("SARVAM_API_KEY", "")
    if not api_key: return b''

    cfg = LANG_TTS_CONFIG.get(lang_key, LANG_TTS_CONFIG["en"])
    payload = {
        "inputs": [text],
        "target_language_code": cfg["target_language_code"],
        "speaker": cfg["speaker"],
        "pitch": 0,
        "pace": 1.0,
        "loudness": 1.5,
        "speech_sample_rate": 8000,
        "enable_preprocessing": True,
        "model": "bulbul:v2",
    }
    headers = {"Content-Type": "application/json", "api-subscription-key": api_key}
    
    try:
        resp = requests.post(SARVAM_TTS_URL, json=payload, headers=headers, timeout=20)
        if resp.ok:
            audio_b64 = resp.json()["audios"][0]
            return base64.b64decode(audio_b64)
    except Exception as e:
        print(f"TTS ERROR: {e}")
    return b''

def save_tts(text: str, lang_key: str, output_path: Path) -> bool:
    audio_bytes = generate_tts(text, lang_key)
    if audio_bytes:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f: f.write(audio_bytes)
        return True
    return False

def generate_tts_stream(text: str, lang_key: str):
    """Generator for streaming TTS audio bytes directly."""
    audio_bytes = generate_tts(text, lang_key)
    if audio_bytes:
        yield audio_bytes
