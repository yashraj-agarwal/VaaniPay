import re

with open('app.py', 'r', encoding='utf-8') as f:
    app_code = f.read()

# Make sure imports for TTS exist
if 'from pathlib import Path' not in app_code:
    app_code = app_code.replace("from mock_db import", "from pathlib import Path\nfrom services.sarvam_tts import save_tts\nfrom mock_db import")

if 'BALANCE_TEMPLATE =' not in app_code:
    templates = """
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
"""
    app_code = app_code.replace("CALL_STATE = {}", f"CALL_STATE = {{}}\n{templates}")

old_upi_success_2 = """
    resp = VoiceResponse()
    if success:
        print(f"✅ Transaction Success! Remaining Balance: Rs {new_balance}")
        play(resp, lang, 'upi_success')
    else:
        print(f"❌ Transaction Failed! Insufficient funds. Balance is: Rs {new_balance}")
        play(resp, lang, 'upi_failed')
    play(resp, lang, 'goodbye')
"""

new_upi_success_2 = """
    resp = VoiceResponse()
    if success:
        print(f"✅ Transaction Success! Remaining Balance: Rs {new_balance}")
        play(resp, lang, 'upi_success')
        
        # --- DYNAMIC TTS GENERATION FOR BALANCE ---
        print("⏳ Generating dynamic Sarvam TTS for remaining balance...")
        text = BALANCE_TEMPLATE.get(lang, BALANCE_TEMPLATE['en']).format(int(new_balance))
        audio_filename = f"dyn_bal_{call_sid}.wav"
        audio_path = Path('prompt_audio') / audio_filename
        
        # Generate the audio block
        if save_tts(text, lang, audio_path):
            resp.play(f"/audio/{audio_filename}")
        # ------------------------------------------
            
    else:
        print(f"❌ Transaction Failed! Insufficient funds. Balance is: Rs {new_balance}")
        play(resp, lang, 'upi_failed')
    play(resp, lang, 'goodbye')
"""
app_code = app_code.replace(old_upi_success_2.strip(), new_upi_success_2.strip())


with open('app.py', 'w', encoding='utf-8') as f:
    f.write(app_code)

print("Balance TTS patch applied.")
