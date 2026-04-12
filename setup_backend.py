import os
import json

# Ensure directories
os.makedirs('data', exist_ok=True)
os.makedirs('services', exist_ok=True)

# 1. MOCK DB JSON FILES
users = {
    "9876543210": {"pin": "1234", "name": "Ramesh Kumar", "lang": "hi", "account_id": "ACC1"},
    "8765432109": {"pin": "5678", "name": "Priya Devi", "lang": "ta", "account_id": "ACC2"},
    "7654321098": {"pin": "9012", "name": "Suresh Babu", "lang": "te", "account_id": "ACC3"}
}
accounts = {
    "ACC1": {"balance": 15000, "pf": 45000, "nps": 120000},
    "ACC2": {"balance": 8200, "pf": 12000, "nps": 25000},
    "ACC3": {"balance": 3500, "pf": 5000, "nps": 8000}
}
with open('data/users.json', 'w') as f: json.dump(users, f, indent=2)
with open('data/accounts.json', 'w') as f: json.dump(accounts, f, indent=2)

# 2. MOCK_DB.PY
mock_db_code = """
import json

def load_json(path):
    try:
        with open(path, 'r') as f: return json.load(f)
    except: return {}

def get_user(phone):
    users = load_json('data/users.json')
    return users.get(phone)

def get_account(acc_id):
    accounts = load_json('data/accounts.json')
    return accounts.get(acc_id)
"""
with open('mock_db.py', 'w') as f: f.write(mock_db_code.strip())

# 3. CONFIG.PY
config_code = """
LANG_CONFIG = {
    "1": "hi", "2": "en", "3": "ta", "4": "te", "5": "kn",
    "6": "ml", "7": "mr", "8": "bn", "9": "gu"
}
"""
with open('config.py', 'w') as f: f.write(config_code.strip())

# 4. APP.PY (The main Flask/Twilio logic)
app_code = """
import os
from flask import Flask, request, Response, jsonify, send_from_directory
from twilio.twiml.voice_response import VoiceResponse, Gather
from mock_db import get_user, get_account
from config import LANG_CONFIG
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
CALL_STATE = {}

def play(response, lang, prompt_name):
    # e.g., 'hi_main_menu.wav'
    audio_url = f"/audio/{lang}_{prompt_name}.wav"
    response.play(audio_url)

@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory('prompt_audio', filename)

@app.route('/', methods=['POST'])
def handle_incoming():
    call_sid = request.form.get('CallSid')
    CALL_STATE[call_sid] = {}
    resp = VoiceResponse()
    gather = Gather(num_digits=1, action='/handle-lang', method='POST')
    play(gather, 'en', 'lang_menu')
    resp.append(gather)
    return Response(str(resp), mimetype='text/xml')

@app.route('/handle-lang', methods=['POST'])
def handle_lang():
    call_sid = request.form.get('CallSid')
    digit = request.form.get('Digits')
    lang = LANG_CONFIG.get(digit, 'en')
    CALL_STATE[call_sid] = {'lang': lang}
    
    resp = VoiceResponse()
    gather = Gather(num_digits=10, action='/handle-phone', method='POST', timeout=15)
    play(gather, lang, 'enter_phone')
    resp.append(gather)
    # If they time out, loop back
    resp.redirect('/handle-lang?Digits=' + digit)
    return Response(str(resp), mimetype='text/xml')

@app.route('/handle-phone', methods=['POST'])
def handle_phone():
    call_sid = request.form.get('CallSid')
    phone = request.form.get('Digits', '').strip()
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    
    if len(phone) < 3:
        # Fallback if timeout happens too quickly
        resp = VoiceResponse()
        resp.redirect('/handle-lang?Digits=' + dict.get('lang', '2'))
        return Response(str(resp), mimetype='text/xml')
        
    user = get_user(phone)
    if not user:
        resp = VoiceResponse()
        play(resp, lang, 'no_account')
        resp.hangup()
        return Response(str(resp), mimetype='text/xml')
        
    state['phone'] = phone
    state['user'] = user
    CALL_STATE[call_sid] = state
    
    resp = VoiceResponse()
    gather = Gather(num_digits=4, action='/handle-mpin', method='POST', timeout=15)
    play(gather, lang, 'enter_mpin')
    resp.append(gather)
    return Response(str(resp), mimetype='text/xml')

@app.route('/handle-mpin', methods=['POST'])
def handle_mpin():
    call_sid = request.form.get('CallSid')
    mpin = request.form.get('Digits')
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    user = state.get('user')
    
    if user['pin'] != mpin:
        resp = VoiceResponse()
        play(resp, lang, 'wrong_mpin')
        resp.hangup()
        return Response(str(resp), mimetype='text/xml')
        
    resp = VoiceResponse()
    play(resp, lang, 'auth_success')
    resp.redirect('/main-menu')
    return Response(str(resp), mimetype='text/xml')

@app.route('/main-menu', methods=['POST'])
def main_menu():
    call_sid = request.form.get('CallSid')
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    
    resp = VoiceResponse()
    gather = Gather(num_digits=1, action='/handle-menu', method='POST')
    play(gather, lang, 'main_menu')
    resp.append(gather)
    return Response(str(resp), mimetype='text/xml')

@app.route('/handle-menu', methods=['POST'])
def handle_menu():
    call_sid = request.form.get('CallSid')
    digit = request.form.get('Digits')
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    user = state.get('user', {})
    
    resp = VoiceResponse()
    if digit == '2':
        # Balance
        acc = get_account(user.get('account_id'))
        # In a real app we would use TTS for the exact amount.
        # Fallback to a static prompt for now.
        play(resp, lang, 'auth_success') 
        resp.redirect('/main-menu')
    elif digit == '3':
        # Loan
        play(resp, lang, 'loan_ask_amount')
        resp.redirect('/main-menu')
    else:
        play(resp, lang, 'invalid')
        resp.redirect('/main-menu')
        
    return Response(str(resp), mimetype='text/xml')

@app.route('/call-complete', methods=['POST'])
def call_complete():
    return '', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
"""
with open('app.py', 'w') as f: f.write(app_code.strip())

print("Backend setup complete.")
