from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from state import CALL_STATE
from config import LANG_CONFIG
from mock_db import get_user
from security import verify_mpin, verify_twilio_signature

router = APIRouter(dependencies=[Depends(verify_twilio_signature)])

def play(response, lang, prompt_name):
    audio_url = f"/audio/{lang}_{prompt_name}.wav"
    response.play(audio_url)

@router.post("/")
@router.post("/prompt-lang")
async def prompt_lang():
    resp = VoiceResponse()
    gather = Gather(
        num_digits=1,
        action='/auth/submit-lang',
        method='POST',
        timeout=8,
        finish_on_key=''
    )
    gather.play('/audio/universal_language_menu.wav')
    resp.append(gather)
    resp.redirect('/auth/prompt-lang')
    return Response(content=str(resp), media_type="application/xml")

@router.post("/submit-lang")
async def submit_lang(request: Request):
    form = await request.form()
    call_sid = form.get('CallSid', '')
    digit = form.get('Digits', '')
    
    if not digit or len(digit) != 1 or digit not in LANG_CONFIG:
        resp = VoiceResponse()
        resp.redirect('/auth/prompt-lang')
        return Response(content=str(resp), media_type="application/xml")
        
    lang = LANG_CONFIG.get(digit)
    CALL_STATE[call_sid] = {'lang': lang}
    
    resp = VoiceResponse()
    resp.redirect('/auth/prompt-phone')
    return Response(content=str(resp), media_type="application/xml")

@router.post("/prompt-phone")
async def prompt_phone(request: Request):
    form = await request.form()
    call_sid = form.get('CallSid', '')
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    
    resp = VoiceResponse()
    gather = Gather(num_digits=10, action='/auth/submit-phone', method='POST', timeout=15)
    play(gather, lang, 'enter_phone')
    resp.append(gather)
    resp.redirect('/auth/prompt-phone')
    return Response(content=str(resp), media_type="application/xml")

@router.post("/submit-phone")
async def submit_phone(request: Request):
    form = await request.form()
    call_sid = form.get('CallSid', '')
    phone = form.get('Digits', '').strip()
    
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    
    if len(phone) < 3:
        resp = VoiceResponse()
        resp.redirect('/auth/prompt-phone')
        return Response(content=str(resp), media_type="application/xml")
        
    user = await get_user(phone)
    if not user:
        resp = VoiceResponse()
        play(resp, lang, 'invalid')
        resp.redirect('/auth/prompt-phone')
        return Response(content=str(resp), media_type="application/xml")
        
    state['phone'] = phone
    state['user'] = user
    CALL_STATE[call_sid] = state
    
    resp = VoiceResponse()
    resp.redirect('/auth/prompt-mpin')
    return Response(content=str(resp), media_type="application/xml")

@router.post("/prompt-mpin")
async def prompt_mpin(request: Request):
    form = await request.form()
    call_sid = form.get('CallSid', '')
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    
    resp = VoiceResponse()
    gather = Gather(num_digits=4, action='/auth/submit-mpin', method='POST', timeout=15)
    play(gather, lang, 'enter_mpin')
    resp.append(gather)
    resp.redirect('/auth/prompt-mpin')
    return Response(content=str(resp), media_type="application/xml")

@router.post("/submit-mpin")
async def submit_mpin(request: Request):
    form = await request.form()
    call_sid = form.get('CallSid', '')
    mpin = form.get('Digits', '')
    
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    user = state.get('user')
    
    if not user:
        resp = VoiceResponse()
        resp.redirect('/auth/prompt-phone')
        return Response(content=str(resp), media_type="application/xml")

    # Rate limiting counter logic
    state['auth_attempts'] = state.get('auth_attempts', 0) + 1
    
    if state['auth_attempts'] > 3:
        resp = VoiceResponse()
        play(resp, lang, 'goodbye') # Play some failure prompt
        resp.hangup()
        return Response(content=str(resp), media_type="application/xml")
        
    if not verify_mpin(mpin, user['pin']):
        CALL_STATE[call_sid] = state
        resp = VoiceResponse()
        play(resp, lang, 'wrong_mpin')
        resp.redirect('/auth/prompt-mpin')
        return Response(content=str(resp), media_type="application/xml")
        
    # Reset attempts on success
    state['auth_attempts'] = 0
    CALL_STATE[call_sid] = state
    
    resp = VoiceResponse()
    play(resp, lang, 'auth_success')
    resp.redirect('/services/prompt-main-menu')
    return Response(content=str(resp), media_type="application/xml")

@router.post("/call-complete")
async def call_complete(request: Request):
    form = await request.form()
    call_sid = form.get('CallSid', '')
    # Cleanup state to prevent memory leak
    if call_sid in CALL_STATE:
        del CALL_STATE[call_sid]
    return Response(content="ok", media_type="text/plain")
