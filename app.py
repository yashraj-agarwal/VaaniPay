import os
from flask import Flask, request, Response, send_from_directory
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from pathlib import Path

from services.sarvam_tts import save_tts
from mock_db import get_user, get_account
from config import LANG_CONFIG
from services.financial_ops import calculate_behavioral_score, perform_upi_transaction
from dotenv import load_dotenv

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
    else:
        # Strict 1-9 check: if anything else (including 0, 8, 9), invalid and repeat
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
    state['recipient'] = recip
    lang = state.get('lang', 'en')
    CALL_STATE[call_sid] = state
    
    resp = VoiceResponse()
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
        except:
            pass # Silent fail: just proceed to amount
        resp.redirect('/prompt-upi-amount')
    else:
        play(resp, lang, 'invalid')
        resp.redirect('/prompt-upi-recipient')
        
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)