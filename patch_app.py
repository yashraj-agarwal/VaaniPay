import re

with open('app.py', 'r', encoding='utf-8') as f:
    app_code = f.read()

# 1. Replace handle_menu logic to include 5, 6, 7
old_handle_menu = """
    elif digit == '4':
        # Insurance
        gather = Gather(num_digits=1, action='/insurance-confirm', method='POST', timeout=8)
        play(gather, lang, 'insurance_menu')
        resp.append(gather)
    else:
        play(resp, lang, 'invalid')
        resp.redirect('/main-menu')
"""

new_handle_menu = """
    elif digit == '4':
        # Insurance
        gather = Gather(num_digits=1, action='/insurance-confirm', method='POST', timeout=8)
        play(gather, lang, 'insurance_menu')
        resp.append(gather)
    elif digit == '5':
        # Credit Score
        play(resp, lang, 'auth_success') # placeholder for 'calculating...'
        play(resp, lang, 'loan_approved') # placeholder for 'score is good'
        resp.redirect('/main-menu')
    elif digit == '6':
        # Savings FD/RD
        gather = Gather(num_digits=1, action='/savings-amount', method='POST', timeout=10)
        play(gather, lang, 'savings_menu')
        resp.append(gather)
    elif digit == '7':
        # PF / NPS
        play(resp, lang, 'auth_success') # placeholder for reading balance
        resp.redirect('/main-menu')
    else:
        play(resp, lang, 'invalid')
        resp.redirect('/main-menu')
"""
app_code = app_code.replace(old_handle_menu.strip(), new_handle_menu.strip())

# 2. Add new savings endpoints before if __name__ == '__main__':
new_routes = """
@app.route('/savings-amount', methods=['POST'])
def savings_amount():
    call_sid = request.form.get('CallSid')
    choice = request.form.get('Digits')
    print(f"👉 [USER INPUT] Savings Type Selected: {choice}")
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    
    resp = VoiceResponse()
    gather = Gather(num_digits=4, action='/savings-duration', method='POST', timeout=10)
    play(gather, lang, 'savings_ask_amount')
    resp.append(gather)
    return Response(str(resp), mimetype='text/xml')

@app.route('/savings-duration', methods=['POST'])
def savings_duration():
    call_sid = request.form.get('CallSid')
    amount = request.form.get('Digits')
    print(f"👉 [USER INPUT] Savings Amount: ₹{amount}")
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    
    resp = VoiceResponse()
    gather = Gather(num_digits=2, action='/savings-success', method='POST', timeout=10)
    play(gather, lang, 'savings_ask_duration')
    resp.append(gather)
    return Response(str(resp), mimetype='text/xml')

@app.route('/savings-success', methods=['POST'])
def savings_success():
    call_sid = request.form.get('CallSid')
    duration = request.form.get('Digits')
    print(f"👉 [USER INPUT] Savings Duration: {duration} months")
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
    
    resp = VoiceResponse()
    play(resp, lang, 'savings_success')
    play(resp, lang, 'goodbye')
    resp.hangup()
    return Response(str(resp), mimetype='text/xml')

"""

app_code = app_code.replace("if __name__ == '__main__':", new_routes + "\nif __name__ == '__main__':")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(app_code)

print("Patch applied to app.py")
