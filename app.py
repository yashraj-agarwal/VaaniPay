import os
from flask import Flask, request, Response, send_from_directory
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from pathlib import Path

from services.sarvam_tts import save_tts
from mock_db import get_user, get_account
from config import LANG_CONFIG
from services.financial_ops import calculate_behavioral_score, perform_upi_transaction
from services.ai_mentor import process_mentor_audio
from dotenv import load_dotenv
import threading

load_dotenv()
app = Flask(__name__)

BALANCE_TEMPLATE = {
    'en': 'Your remaining balance is rupees {}',
    'hi': 'Aapka shesh balance hai {} rupay',
    'ta': 'Ungal meedhi iruppu rubai {}',
    'te': 'Mee migilina balance {} rupayilu',
    'kn': 'Nimmalli uLida byalens {} rupayi',
    'ml': 'Ningalude baaki balance {} roopa aanu',
    'mr': 'Tumcha shillak balance ahe {} rupaye',
    'bn': 'Aapnar baki balance {} taka',
    'gu': 'Tamarun baki balance chhe {} rupiya'
}

CALL_STATE = {}
MENTOR_RESULTS = {}  # call_sid -> audio filename, 'PROCESSING', or 'ERROR'

def play(response, lang, prompt_name):
    audio_url = f"/audio/{lang}_{prompt_name}.wav"
    response.play(audio_url)

@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory('prompt_audio', filename)

# ----------------- INTRO & AUTH -----------------

@app.route('/', methods=['GET', 'POST'])
def handle_incoming():
    call_sid = request.values.get('CallSid')
    CALL_STATE[call_sid] = {}
    return redirect_to_prompt('/prompt-lang')

@app.route('/prompt-lang', methods=['GET', 'POST'])
def prompt_lang():
    resp = VoiceResponse()
    # num_digits=1: stop IMMEDIATELY after exactly 1 keypress
    # timeout=8: wait 8 seconds max, then repeat via redirect
    # finishOnKey='': don't let '#' or '*' end early — enforce exactly 1 DTMF tone
    gather = Gather(
        num_digits=1,
        action='/submit-lang',
        method='POST',
        timeout=8,
        finish_on_key=''
    )
    play(gather, 'en', 'lang_menu')
    resp.append(gather)
    resp.redirect('/prompt-lang')  # Silently loop if no input
    return Response(str(resp), mimetype='text/xml')

@app.route('/submit-lang', methods=['GET', 'POST'])
def submit_lang():
    call_sid = request.values.get('CallSid')
    digit = request.values.get('Digits')
    print(f"👉 [USER INPUT] User selected language digit: {digit}")
    
    # Strict validation: must be exactly 1 digit AND in range 1-9
    if not digit or len(digit) != 1 or digit not in LANG_CONFIG:
        print(f"   [INVALID] '{digit}' is not a valid language choice — looping back")
        resp = VoiceResponse()
        resp.redirect('/prompt-lang')
        return Response(str(resp), mimetype='text/xml')
        
    lang = LANG_CONFIG.get(digit)
    CALL_STATE[call_sid] = {'lang': lang}
    
    resp = VoiceResponse()
    resp.redirect('/prompt-phone')
    return Response(str(resp), mimetype='text/xml')

@app.route('/prompt-phone', methods=['GET', 'POST'])
def prompt_phone():
    call_sid = request.values.get('CallSid')
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    resp = VoiceResponse()
    gather = Gather(num_digits=10, action='/submit-phone', method='POST', timeout=15)
    play(gather, lang, 'enter_phone')
    resp.append(gather)
    resp.redirect('/prompt-phone')
    return Response(str(resp), mimetype='text/xml')

@app.route('/submit-phone', methods=['GET', 'POST'])
def submit_phone():
    call_sid = request.values.get('CallSid')
    phone = request.values.get('Digits', '').strip()
    print(f"👉 [USER INPUT] User entered phone number: {phone}")
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    
    if len(phone) < 3:
        resp = VoiceResponse()
        resp.redirect('/prompt-phone')
        return Response(str(resp), mimetype='text/xml')
        
    user = get_user(phone)
    if not user:
        resp = VoiceResponse()
        play(resp, lang, 'invalid')
        resp.redirect('/prompt-phone')
        return Response(str(resp), mimetype='text/xml')
        
    state['phone'] = phone
    state['user'] = user
    CALL_STATE[call_sid] = state
    
    resp = VoiceResponse()
    resp.redirect('/prompt-mpin')
    return Response(str(resp), mimetype='text/xml')

@app.route('/prompt-mpin', methods=['GET', 'POST'])
def prompt_mpin():
    call_sid = request.values.get('CallSid')
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    resp = VoiceResponse()
    gather = Gather(num_digits=4, action='/submit-mpin', method='POST', timeout=15)
    play(gather, lang, 'enter_mpin')
    resp.append(gather)
    resp.redirect('/prompt-mpin')
    return Response(str(resp), mimetype='text/xml')

@app.route('/submit-mpin', methods=['GET', 'POST'])
def submit_mpin():
    call_sid = request.values.get('CallSid')
    mpin = request.values.get('Digits')
    print(f"👉 [USER INPUT] User entered mPIN: {mpin}")
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    user = state.get('user')
    
    if user['pin'] != mpin:
        resp = VoiceResponse()
        play(resp, lang, 'wrong_mpin')
        resp.redirect('/prompt-mpin')
        return Response(str(resp), mimetype='text/xml')
        
    resp = VoiceResponse()
    play(resp, lang, 'auth_success')
    resp.redirect('/prompt-main-menu')
    return Response(str(resp), mimetype='text/xml')

# ----------------- MAIN MENU -----------------

@app.route('/prompt-main-menu', methods=['GET', 'POST'])
def prompt_main_menu():
    call_sid = request.values.get('CallSid')
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    
    resp = VoiceResponse()
    gather = Gather(num_digits=1, action='/submit-main-menu', method='POST', timeout=12)
    play(gather, lang, 'main_menu')
    resp.append(gather)
    resp.redirect('/prompt-main-menu') # Loop on timeout
    return Response(str(resp), mimetype='text/xml')

@app.route('/submit-main-menu', methods=['GET', 'POST'])
def submit_main_menu():
    call_sid = request.values.get('CallSid')
    digit = request.values.get('Digits')
    print(f"👉 [USER INPUT] User selected main menu option: {digit}")
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    user = state.get('user', {})
    
    resp = VoiceResponse()
    if digit == '1': # UPI Payment
        resp.redirect('/prompt-upi-recipient')
    elif digit == '2': # Balance
        acc = get_account(user.get('account_id'))
        balance = acc.get('balance', 0)
        print(f"👉 Reading Balance: Rs {balance}")
        
        text = BALANCE_TEMPLATE.get(lang, BALANCE_TEMPLATE['en']).format(int(balance))
        audio_filename = f"dyn_bal_{call_sid}.wav"
        audio_path = Path('prompt_audio') / audio_filename
        
        try:
            if save_tts(text, lang, audio_path):
                resp.play(f"/audio/{audio_filename}")
            else:
                play(resp, lang, 'auth_success')
        except Exception as e:
            print("TTS failed:", e)
            play(resp, lang, 'auth_success')
        resp.redirect('/prompt-main-menu')
        
    elif digit == '3': # Loan
        resp.redirect('/prompt-loan-amount')
    elif digit == '4': # Insurance
        resp.redirect('/prompt-insurance')
    elif digit == '5': # Credit Score
        print("\\n=== 🧠 CALCULATING BEHAVIORAL CREDIT SCORE ===")
        score, factors = calculate_behavioral_score(user.get('phone', '9876543210'))
        print(f"👉 Generated Score: {score}/900")
        print(f"👉 Key Factors: {', '.join(factors)}")
        print("==============================================\\n")
        play(resp, lang, 'auth_success') 
        play(resp, lang, 'loan_approved') 
        resp.redirect('/prompt-main-menu')
    elif digit == '6': # Savings
        resp.redirect('/prompt-savings-amount')
    elif digit == '7': # PF / NPS
        play(resp, lang, 'auth_success') 
        resp.redirect('/prompt-main-menu')
    elif digit == '8': # Financial Mentor Mode
        resp.redirect('/mentor/start')
    else:
        # Strict 1-9 check: if anything else (including 0, 9), invalid and repeat
        play(resp, lang, 'invalid')
        resp.redirect('/prompt-main-menu')
        
    return Response(str(resp), mimetype='text/xml')

# ----------------- UPI PAYMENT -----------------

@app.route('/prompt-upi-recipient', methods=['GET', 'POST'])
def prompt_upi_recipient():
    call_sid = request.values.get('CallSid')
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    
    resp = VoiceResponse()
    gather = Gather(num_digits=10, action='/submit-upi-recipient', method='POST', timeout=12)
    play(gather, lang, 'upi_ask_recipient')
    resp.append(gather)
    resp.redirect('/prompt-upi-recipient')
    return Response(str(resp), mimetype='text/xml')

@app.route('/submit-upi-recipient', methods=['GET', 'POST'])
def submit_upi_recipient():
    call_sid = request.values.get('CallSid')
    recip = request.values.get('Digits')
    print(f"👉 [USER INPUT] UPI Recipient: {recip}")
    
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    
    # Hard validate: must be exactly 10 digits
    if not recip or len(recip) != 10 or not recip.isdigit():
        print(f"   [INVALID] Recipient '{recip}' is not a valid 10-digit number")
        resp = VoiceResponse()
        play(resp, lang, 'invalid')
        resp.redirect('/prompt-upi-recipient')
        return Response(str(resp), mimetype='text/xml')
    
    # Save the recipient regardless
    state['recipient'] = recip
    CALL_STATE[call_sid] = state
    
    resp = VoiceResponse()
    
    # OPTIONAL: If they are a registered VaaniPay user, speak their name
    recip_user = get_user(recip)
    if recip_user:
        name = recip_user.get('name', 'User')
        text = f"Sending money to {name}."
        if lang == 'hi': text = f"{name} ko paise bheje jayenge."
        
        print(f"⏳ Generating dynamic TTS for recipient: {name}")
        audio_filename = f"dyn_name_{call_sid}.wav"
        audio_path = Path('prompt_audio') / audio_filename
        try:
            if save_tts(text, lang, audio_path):
                resp.play(f"/audio/{audio_filename}")
        except Exception as e:
            print(f"   TTS failed: {e}")
    else:
        # Non-registered user — still valid, just proceed silently
        print(f"   Recipient {recip} is not a VaaniPay user — proceeding to amount")
    
    resp.redirect('/prompt-upi-amount')
    return Response(str(resp), mimetype='text/xml')

@app.route('/prompt-upi-amount', methods=['GET', 'POST'])
def prompt_upi_amount():
    call_sid = request.values.get('CallSid')
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    
    resp = VoiceResponse()
    gather = Gather(num_digits=4, action='/submit-upi-success', method='POST', timeout=12)
    play(gather, lang, 'upi_ask_amount')
    resp.append(gather)
    resp.redirect('/prompt-upi-amount')
    return Response(str(resp), mimetype='text/xml')

@app.route('/submit-upi-success', methods=['GET', 'POST'])
def submit_upi_success():
    call_sid = request.values.get('CallSid')
    amount = request.values.get('Digits')
    if not amount: amount = "0"
    print(f"👉 [USER INPUT] UPI Amount: Rs {amount}")
    
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    user_phone = state.get('phone', '9876543210')
    
    print(f"\\n💸 Processing transaction for user {user_phone}...")
    success, new_balance = perform_upi_transaction(user_phone, amount)
    
    resp = VoiceResponse()
    if success:
        print(f"✅ Transaction Success! Remaining Balance: Rs {new_balance}")
        
        # --- SEND ACTUAL SMS VIA TWILIO ---
        try:
            twilio_client = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))
            recip = state.get('recipient')
            if recip:
                recip_formatted = f"+91{recip}" if len(recip) == 10 else recip
                msg_body = f"VaaniPay Alert: Rs {amount} has been successfully deposited into your account from {user_phone}."
                twilio_client.messages.create(
                    body=msg_body,
                    from_=os.getenv('TWILIO_PHONE_NUMBER'),
                    to=recip_formatted
                )
                print(f"📧 MAGIC TRICK: Real SMS fired to {recip_formatted}!")
        except Exception as e:
            print(f"⚠️ Could not send SMS: {e}")
        # ----------------------------------
        
        play(resp, lang, 'upi_success')
        
        # --- DYNAMIC TTS GENERATION FOR BALANCE ---
        print("⏳ Generating dynamic Sarvam TTS for remaining balance...")
        text = BALANCE_TEMPLATE.get(lang, BALANCE_TEMPLATE['en']).format(int(new_balance))
        audio_filename = f"dyn_bal_{call_sid}.wav"
        audio_path = Path('prompt_audio') / audio_filename
        
        try:
            if save_tts(text, lang, audio_path):
                resp.play(f"/audio/{audio_filename}")
        except Exception as e:
            print("TTS failed:", e)
    else:
        print(f"❌ Transaction Failed! Insufficient funds. Balance is: Rs {new_balance}")
        play(resp, lang, 'upi_failed')
        
        print("⏳ Generating dynamic Sarvam TTS for insufficient balance...")
        text = BALANCE_TEMPLATE.get(lang, BALANCE_TEMPLATE['en']).format(int(new_balance))
        audio_filename = f"dyn_bal_fail_{call_sid}.wav"
        audio_path = Path('prompt_audio') / audio_filename
        try:
            if save_tts(text, lang, audio_path):
                resp.play(f"/audio/{audio_filename}")
        except Exception as e:
            print("TTS failed:", e)

    resp.redirect('/prompt-main-menu')
    return Response(str(resp), mimetype='text/xml')

# ----------------- OTHER SUB MENUS -----------------

@app.route('/prompt-loan-amount', methods=['GET', 'POST'])
def prompt_loan_amount():
    call_sid = request.values.get('CallSid')
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    resp = VoiceResponse()
    gather = Gather(num_digits=4, action='/submit-loan', method='POST', timeout=10)
    play(gather, lang, 'loan_ask_amount')
    resp.append(gather)
    resp.redirect('/prompt-loan-amount')
    return Response(str(resp), mimetype='text/xml')

@app.route('/submit-loan', methods=['GET', 'POST'])
def submit_loan():
    call_sid = request.values.get('CallSid')
    amount = request.values.get('Digits')
    print(f"👉 [USER INPUT] Loan Amount request: Rs {amount}")
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    resp = VoiceResponse()
    play(resp, lang, 'loan_approved')
    resp.redirect('/prompt-main-menu')
    return Response(str(resp), mimetype='text/xml')

@app.route('/prompt-insurance', methods=['GET', 'POST'])
def prompt_insurance():
    call_sid = request.values.get('CallSid')
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    resp = VoiceResponse()
    gather = Gather(num_digits=1, action='/submit-insurance', method='POST', timeout=8)
    play(gather, lang, 'insurance_menu')
    resp.append(gather)
    resp.redirect('/prompt-insurance')
    return Response(str(resp), mimetype='text/xml')

@app.route('/submit-insurance', methods=['GET', 'POST'])
def submit_insurance():
    call_sid = request.values.get('CallSid')
    choice = request.values.get('Digits')
    print(f"👉 [USER INPUT] Insurance Selected: {choice}")
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    resp = VoiceResponse()
    if choice in ['1', '2']:
        play(resp, lang, 'insurance_success')
        resp.redirect('/prompt-main-menu')
    else:
        play(resp, lang, 'invalid')
        resp.redirect('/prompt-insurance')
    return Response(str(resp), mimetype='text/xml')

@app.route('/prompt-savings-amount', methods=['GET', 'POST'])
def prompt_savings_amount():
    call_sid = request.values.get('CallSid')
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    resp = VoiceResponse()
    gather = Gather(num_digits=4, action='/prompt-savings-duration', method='POST', timeout=10)
    play(gather, lang, 'savings_ask_amount')
    resp.append(gather)
    resp.redirect('/prompt-savings-amount')
    return Response(str(resp), mimetype='text/xml')

@app.route('/prompt-savings-duration', methods=['GET', 'POST'])
def prompt_savings_duration():
    call_sid = request.values.get('CallSid')
    amount = request.values.get('Digits')
    state = CALL_STATE.get(call_sid, {})
    if amount: state['savings_amt'] = amount
    CALL_STATE[call_sid] = state
    
    lang = state.get('lang', 'en')
    resp = VoiceResponse()
    gather = Gather(num_digits=2, action='/submit-savings', method='POST', timeout=10)
    play(gather, lang, 'savings_ask_duration')
    resp.append(gather)
    resp.redirect('/prompt-savings-duration')
    return Response(str(resp), mimetype='text/xml')

@app.route('/submit-savings', methods=['GET', 'POST'])
def submit_savings():
    call_sid = request.values.get('CallSid')
    duration = request.values.get('Digits')
    print(f"👉 [USER INPUT] Savings Duration: {duration} months")
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    
    resp = VoiceResponse()
    play(resp, lang, 'savings_success')
    resp.redirect('/prompt-main-menu')
    return Response(str(resp), mimetype='text/xml')

def redirect_to_prompt(route):
    resp = VoiceResponse()
    resp.redirect(route)
    return Response(str(resp), mimetype='text/xml')

# ================== FINANCIAL MENTOR MODE ==================

@app.route('/mentor/start', methods=['GET', 'POST'])
def mentor_start():
    call_sid = request.values.get('CallSid')
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')

    # Enrich session with user's financial data for LLM context
    user = state.get('user', {})
    acc = get_account(user.get('account_id', ''))
    _, factors = calculate_behavioral_score(state.get('phone', ''))
    score = factors  # reuse score
    state['balance'] = acc.get('balance', 0)
    state['credit_score'] = 650  # mock default
    CALL_STATE[call_sid] = state

    print(f"\n=== AI FINANCIAL MENTOR STARTED (lang={lang}) ===")
    resp = VoiceResponse()

    # Generate intro in selected language
    intro_texts = {
        'en': 'Welcome to VaaniPay Financial Mentor. Ask me any financial question after the beep.',
        'hi': 'VaaniPay Financial Mentor mein aapka swagat hai. Beep ke baad apna sawaal poochein.',
        'ta': 'VaaniPay Financial Mentor-il ungalai varuverpagiren. Beep-ku piragu ungal kelvi kelunga.',
        'te': 'VaaniPay Financial Mentor lo swaagatam. Beep taravata mee prashna adugandi.',
        'kn': 'VaaniPay Financial Mentor ge swagatha. Beep nantara nimma prashne keeli.',
        'ml': 'VaaniPay Financial Mentor il swagatham. Beep-inu sesham ninagal chodyam chodyikku.',
        'mr': 'VaaniPay Financial Mentor madhye swagat. Beep nantar tumcha prashna vicharaa.',
        'bn': 'VaaniPay Financial Mentor e swagato. Beep er pore apanar proshno jiggesh korun.',
        'gu': 'VaaniPay Financial Mentor ma swagat chhe. Beep pachhi tamaro prashna poochho.',
    }
    intro_text = intro_texts.get(lang, intro_texts['en'])
    intro_file = f"dynamic_audio/mentor_intro_{call_sid}.wav"
    try:
        save_tts(intro_text, lang, Path(intro_file))
        resp.play(f'/dynamic-audio/mentor_intro_{call_sid}.wav')
    except:
        pass  # fallback to silent start

    resp.redirect('/mentor/listen')
    return Response(str(resp), mimetype='text/xml')


@app.route('/mentor/listen', methods=['GET', 'POST'])
def mentor_listen():
    """Prompt user to speak and start recording."""
    call_sid = request.values.get('CallSid')
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')

    resp = VoiceResponse()

    # Brief beep via Say (Twilio built-in) then record
    resp.say(".")
    resp.record(
        action='/mentor/process',
        method='POST',
        max_length=30,
        finish_on_key='#',
        play_beep=True,
        timeout=5,
    )
    # If no speech recorded, loop back
    resp.redirect('/mentor/listen')
    return Response(str(resp), mimetype='text/xml')


@app.route('/mentor/process', methods=['GET', 'POST'])
def mentor_process():
    """Receive Twilio recording. Immediately start background thread and return a pause."""
    call_sid = request.values.get('CallSid')
    recording_url = request.values.get('RecordingUrl', '')
    recording_duration = int(request.values.get('RecordingDuration', 0))
    print(f"\n   [MENTOR] Recording received. Duration={recording_duration}s")

    state = CALL_STATE.get(call_sid, {})
    resp = VoiceResponse()

    if recording_duration < 1:
        print("   [MENTOR] Recording too short — looping back")
        resp.redirect('/mentor/listen')
        return Response(str(resp), mimetype='text/xml')

    # Mark as processing
    MENTOR_RESULTS[call_sid] = 'PROCESSING'

    # Kick off background thread immediately — don't block Twilio
    def _bg_process():
        print(f"   [MENTOR-THREAD] Starting pipeline for {call_sid}")
        result = process_mentor_audio(recording_url, call_sid, state)
        MENTOR_RESULTS[call_sid] = result if result else 'ERROR'
        print(f"   [MENTOR-THREAD] Done. Result={MENTOR_RESULTS[call_sid]}")

    thread = threading.Thread(target=_bg_process, daemon=True)
    thread.start()

    # Return immediately — pause for 8s then poll for result
    resp.pause(length=8)
    resp.redirect('/mentor/check-result')
    return Response(str(resp), mimetype='text/xml')


@app.route('/mentor/check-result', methods=['GET', 'POST'])
def mentor_check_result():
    """Poll for background processing result. Loop with short pauses until done."""
    call_sid = request.values.get('CallSid')
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    result = MENTOR_RESULTS.get(call_sid, 'ERROR')

    resp = VoiceResponse()
    if result == 'PROCESSING':
        # Still working — wait 3 more seconds and check again
        print(f"   [MENTOR] Still processing for {call_sid}... waiting 3s more")
        resp.pause(length=3)
        resp.redirect('/mentor/check-result')
    elif result != 'ERROR' and result:
        # Done! Redirect to respond with the audio filename
        print(f"   [MENTOR] Result ready: {result}")
        resp.redirect(f'/mentor/respond?audio={result}')
    else:
        # Something failed — play error in language
        error_texts = {
            'en': 'Sorry, I did not understand. Please speak again.',
            'hi': 'Maafi chahta hoon, samajh nahi aaya. Kripya phir se bolein.',
            'ta': 'Mannikavum, puriyavillai. Meedum paesunga.',
            'te': 'Nenu artham chesukoledu. Malli cheppandi.',
            'kn': 'Kshamissi, artha aagalilla. Matte heli.',
            'ml': 'Manasilaayilla. Onnu koodi parayan.',
            'mr': 'Samajale nahi. Parat sanga.',
            'bn': 'Bujhte parini. Abar bolun.',
            'gu': 'Samajhyu nahi. Pharthi bolo.',
        }
        resp.say(error_texts.get(lang, error_texts['en']))
        resp.redirect('/mentor/listen')

    return Response(str(resp), mimetype='text/xml')


@app.route('/mentor/respond', methods=['GET', 'POST'])
def mentor_respond():
    """Play AI response, then loop back for next question."""
    call_sid = request.values.get('CallSid')
    audio_filename = request.values.get('audio', '')
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')

    resp = VoiceResponse()

    # Play the AI generated response
    if audio_filename:
        resp.play(f'/dynamic-audio/{audio_filename}')

    # Prompt for next question
    followup_texts = {
        'en': 'You can ask another question, or press star to return to the main menu.',
        'hi': 'Aap aur sawaal pooch sakte hain, ya star dabakar main menu mein wapas ja sakte hain.',
        'ta': 'Vera kelvi keelungal, illatha star aruththa main menu-ku tirumbunga.',
        'te': 'Meru minka prashna adugavaccham, leda star noccite main menu ki tirigi vastam.',
        'kn': 'Inka prashne keeyabahudhu, athava star odisi main menu ge hodha.',
        'ml': 'Merre chodyam chodyikkam, athava star arakkam main menu il maadam.',
        'mr': 'Tumhi aankhi prashna vicharaar, kinva star daabaa ani main menu la parat ya.',
        'bn': 'Ar proshno korte paren, ba star chhapa main menu te phire jan.',
        'gu': 'Bijo prashn pu chhho, athwa star dabavine main menu par pachi jao.',
    }
    followup_text = followup_texts.get(lang, followup_texts['en'])
    followup_file = f"dynamic_audio/mentor_followup_{call_sid}.wav"
    try:
        save_tts(followup_text, lang, Path(followup_file))
        resp.play(f'/dynamic-audio/mentor_followup_{call_sid}.wav')
    except:
        resp.say(followup_text)

    # Record the next question — pressing * goes back to main menu
    resp.record(
        action='/mentor/process',
        method='POST',
        max_length=30,
        finish_on_key='*',
        play_beep=True,
        timeout=5,
    )
    # * pressed => back to main menu
    resp.redirect('/prompt-main-menu')
    return Response(str(resp), mimetype='text/xml')


@app.route('/dynamic-audio/<filename>')
def serve_dynamic_audio(filename):
    """Serve dynamically generated mentor audio files."""
    return send_from_directory('dynamic_audio', filename)

# ===========================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)