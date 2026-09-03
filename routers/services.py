from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response, StreamingResponse
from twilio.twiml.voice_response import VoiceResponse, Gather
from state import CALL_STATE, BALANCE_TEMPLATE
from config import LANG_CONFIG
from mock_db import get_account, get_user
from services.financial_ops import calculate_behavioral_score, perform_upi_transaction
from services.sarvam_tts import generate_tts_stream
from security import verify_twilio_signature

router = APIRouter(dependencies=[Depends(verify_twilio_signature)])

def play(response, lang, prompt_name):
    audio_url = f"/audio/{lang}_{prompt_name}.wav"
    response.play(audio_url)

@router.post("/prompt-main-menu")
async def prompt_main_menu(request: Request):
    form = await request.form()
    call_sid = form.get('CallSid', '')
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    
    resp = VoiceResponse()
    gather = Gather(num_digits=1, action='/services/submit-main-menu', method='POST', timeout=15)
    play(gather, lang, 'main_menu')
    resp.append(gather)
    resp.redirect('/services/prompt-main-menu')
    return Response(content=str(resp), media_type="application/xml")

@router.post("/submit-main-menu")
async def submit_main_menu(request: Request):
    form = await request.form()
    call_sid = form.get('CallSid', '')
    digit = form.get('Digits', '')
    
    if digit == '1': return await prompt_upi(request)
    if digit == '2': return await check_balance(request)
    if digit == '3': return await check_loan_eligibility(request)
    # 4 is AI Mentor, handled in mentor.py or we can redirect
    if digit == '4':
        resp = VoiceResponse()
        resp.redirect('/mentor/prompt')
        return Response(content=str(resp), media_type="application/xml")
        
    resp = VoiceResponse()
    resp.redirect('/services/prompt-main-menu')
    return Response(content=str(resp), media_type="application/xml")

@router.post("/prompt-upi")
async def prompt_upi(request: Request):
    form = await request.form()
    call_sid = form.get('CallSid', '')
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    
    resp = VoiceResponse()
    gather = Gather(num_digits=10, action='/services/submit-upi-phone', method='POST', timeout=15)
    play(gather, lang, 'upi_enter_phone')
    resp.append(gather)
    resp.redirect('/services/prompt-upi')
    return Response(content=str(resp), media_type="application/xml")

@router.post("/submit-upi-phone")
async def submit_upi_phone(request: Request):
    form = await request.form()
    call_sid = form.get('CallSid', '')
    phone = form.get('Digits', '')
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    
    # Just validate length for mock
    if len(phone) < 3:
        resp = VoiceResponse()
        resp.redirect('/services/prompt-upi')
        return Response(content=str(resp), media_type="application/xml")
        
    CALL_STATE[call_sid]['upi_target'] = phone
    
    resp = VoiceResponse()
    gather = Gather(action='/services/submit-upi-amount', method='POST', timeout=15, finish_on_key='#')
    play(gather, lang, 'upi_enter_amount')
    resp.append(gather)
    resp.redirect('/services/prompt-upi-amount')
    return Response(content=str(resp), media_type="application/xml")

@router.post("/submit-upi-amount")
async def submit_upi_amount(request: Request):
    form = await request.form()
    call_sid = form.get('CallSid', '')
    amount = form.get('Digits', '')
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    user = state.get('user')
    
    if not amount:
        resp = VoiceResponse()
        resp.redirect('/services/prompt-upi-amount')
        return Response(content=str(resp), media_type="application/xml")
        
    success, new_bal = await perform_upi_transaction(user['phone'], amount)
    
    resp = VoiceResponse()
    if success:
        # Instead of saving dynamically, we point to our new dynamic stream endpoint
        text = f"Payment of rupees {amount} successful. New balance is {new_bal}."
        # Twilio needs an absolute or relative URL
        resp.play(f"/dynamic-audio/generate?text={text}&lang={lang}")
    else:
        play(resp, lang, 'upi_failed')
        
    play(resp, lang, 'return_menu')
    gather = Gather(num_digits=1, action='/services/return-menu', method='POST', timeout=10)
    resp.append(gather)
    return Response(content=str(resp), media_type="application/xml")

@router.post("/check-balance")
async def check_balance(request: Request):
    form = await request.form()
    call_sid = form.get('CallSid', '')
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    user = state.get('user')
    
    acc = await get_account(user['account_id'])
    bal = acc.get('balance', 0)
    
    text = BALANCE_TEMPLATE.get(lang, BALANCE_TEMPLATE['en']).format(bal)
    
    resp = VoiceResponse()
    resp.play(f"/dynamic-audio/generate?text={text}&lang={lang}")
    play(resp, lang, 'return_menu')
    gather = Gather(num_digits=1, action='/services/return-menu', method='POST', timeout=10)
    resp.append(gather)
    return Response(content=str(resp), media_type="application/xml")

@router.post("/check-loan-eligibility")
async def check_loan_eligibility(request: Request):
    form = await request.form()
    call_sid = form.get('CallSid', '')
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    user = state.get('user')
    
    score, factors = await calculate_behavioral_score(user['phone'])
    
    if score >= 700:
        text = f"Congratulations, your score is {score}. You are eligible for a pre-approved loan of up to 50,000 rupees."
    elif score >= 500:
        text = f"Your score is {score}. You are eligible for a small credit line of up to 5000 rupees."
    else:
        text = f"Your score is {score}. Currently you are not eligible for a loan. Keep maintaining your balance to improve your score."
        
    resp = VoiceResponse()
    resp.play(f"/dynamic-audio/generate?text={text}&lang={lang}")
    play(resp, lang, 'return_menu')
    gather = Gather(num_digits=1, action='/services/return-menu', method='POST', timeout=10)
    resp.append(gather)
    return Response(content=str(resp), media_type="application/xml")

@router.post("/return-menu")
async def return_menu(request: Request):
    resp = VoiceResponse()
    resp.redirect('/services/prompt-main-menu')
    return Response(content=str(resp), media_type="application/xml")
