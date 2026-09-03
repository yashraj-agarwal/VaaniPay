from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse
from routers import auth, services, mentor
from services.sarvam_tts import generate_tts_stream
import os
from pathlib import Path

app = FastAPI(title="VaaniPay Voice Backend", version="2.0.0")

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(services.router, prefix="/services", tags=["services"])
app.include_router(mentor.router, prefix="/mentor", tags=["mentor"])

BASE_DIR = Path(__file__).parent
PROMPT_AUDIO_DIR = BASE_DIR / "prompt_audio"

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    file_path = PROMPT_AUDIO_DIR / filename
    if not file_path.exists():
        # Return a fallback or 404
        return Response(status_code=404)
    return FileResponse(path=file_path, media_type="audio/wav")

@app.get("/dynamic-audio/generate")
async def generate_dynamic_audio(text: str, lang: str):
    """Streams TTS audio directly without saving to disk."""
    return StreamingResponse(
        generate_tts_stream(text, lang), 
        media_type="audio/wav"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
