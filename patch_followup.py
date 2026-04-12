import re

with open('app.py', 'r', encoding='utf-8') as f:
    app_code = f.read()

# Make sure imports exist
if 'from services.financial_ops import' not in app_code:
    app_code = app_code.replace("from config import LANG_CONFIG", "from config import LANG_CONFIG\nfrom services.financial_ops import calculate_behavioral_score, perform_upi_transaction")

# Replace Credit Score Logic
old_credit_logic = """
    elif digit == '5':
        # Credit Score
        play(resp, lang, 'auth_success') # placeholder for 'calculating...'
        play(resp, lang, 'loan_approved') # placeholder for 'score is good'
        resp.redirect('/main-menu')
"""

new_credit_logic = """
    elif digit == '5':
        # Credit Score
        print("\\n=== 🧠 CALCULATING BEHAVIORAL CREDIT SCORE ===")
        score, factors = calculate_behavioral_score(user.get('phone', '9876543210'))
        print(f"👉 Generated Score: {score}/900")
        print(f"👉 Key Factors: {', '.join(factors)}")
        print("==============================================\\n")
        play(resp, lang, 'auth_success') # placeholder for 'calculating...'
        play(resp, lang, 'loan_approved') # placeholder for 'score is good'
        resp.redirect('/main-menu')
"""
app_code = app_code.replace(old_credit_logic.strip(), new_credit_logic.strip())

# Add UPI transaction updating
old_upi_success = """
@app.route('/upi-success', methods=['POST'])
def upi_success():
    call_sid = request.form.get('CallSid')
    amount = request.form.get('Digits')
    print(f"👉 [USER INPUT] UPI Amount: \u20b9{amount}")
    lang = CALL_STATE.get(call_sid, {}).get('lang', 'en')
"""

new_upi_success = """
@app.route('/upi-success', methods=['POST'])
def upi_success():
    call_sid = request.form.get('CallSid')
    amount = request.form.get('Digits')
    print(f"👉 [USER INPUT] UPI Amount: Rs {amount}")
    
    state = CALL_STATE.get(call_sid, {})
    lang = state.get('lang', 'en')
    user_phone = state.get('phone', '9876543210')
    
    print(f"\\n💸 Processing transacation for user {user_phone}...")
    success, new_balance = perform_upi_transaction(user_phone, amount)
"""
app_code = app_code.replace(old_upi_success.strip(), new_upi_success.strip())

old_upi_success_2 = """
    resp = VoiceResponse()
    play(resp, lang, 'upi_success')
    play(resp, lang, 'goodbye')
"""

new_upi_success_2 = """
    resp = VoiceResponse()
    if success:
        print(f"✅ Transaction Success! Remaining Balance: Rs {new_balance}")
        play(resp, lang, 'upi_success')
    else:
        print(f"❌ Transaction Failed! Insufficient funds. Balance is: Rs {new_balance}")
        play(resp, lang, 'upi_failed')
    play(resp, lang, 'goodbye')
"""
app_code = app_code.replace(old_upi_success_2.strip(), new_upi_success_2.strip())

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(app_code)

print("Second patch applied.")
