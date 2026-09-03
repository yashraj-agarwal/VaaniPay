from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from state import CALL_STATE
from services.ai_mentor import get_mentor_response
from security import verify_twilio_signature

router = APIRouter(dependencies=[Depends(verify_twilio_signature)])

def play(response, lang, prompt_name):
    audio_url = f"/audio/{lang}_{prompt_name}.wav"
    response.play(audio_url)

@router.post("/prompt")
async def mentor_prompt(request: Request):
    form = await request.form()
    call_sid = form.get('CallSid', '')
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    
    resp = VoiceResponse()
    # Twilio speech recognition
    gather = Gather(
        input='speech',
        action='/mentor/process',
        method='POST',
        timeout=5,
        language=lang + "-IN" if lang != 'en' else "en-IN"
    )
    play(gather, lang, 'mentor_welcome')
    resp.append(gather)
    # If no speech, go back to main menu
    resp.redirect('/services/prompt-main-menu')
    return Response(content=str(resp), media_type="application/xml")

@router.post("/process")
async def process_mentor(request: Request):
    form = await request.form()
    call_sid = form.get('CallSid', '')
    speech_result = form.get('SpeechResult', '')
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    user = CALL_STATE.get(call_sid, {}).get('user')
    
    if not speech_result:
        resp = VoiceResponse()
        resp.redirect('/services/prompt-main-menu')
        return Response(content=str(resp), media_type="application/xml")
        
    ai_text = await get_mentor_response(user['phone'], speech_result, lang)
    
    resp = VoiceResponse()
    resp.play(f"/dynamic-audio/generate?text={ai_text}&lang={lang}")
    
    # Ask if they want more help
    gather = Gather(
        input='speech',
        action='/mentor/process',
        method='POST',
        timeout=5,
        language=lang + "-IN" if lang != 'en' else "en-IN"
    )
    play(gather, lang, 'mentor_anything_else')
    resp.append(gather)
    resp.redirect('/services/prompt-main-menu')
    return Response(content=str(resp), media_type="application/xml")
