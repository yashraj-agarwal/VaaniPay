# VaaniPay IVR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a voice-first IVR financial inclusion platform (VaaniPay) using Twilio + Flask + Sarvam AI that lets anyone with a phone access UPI payments, micro-loans, insurance, credit scoring, and savings entirely by voice in 9 Indian languages.

**Architecture:** Flask server handles Twilio TwiML webhooks; all static audio prompts are pre-generated via Sarvam AI TTS and served as MP3 files; dynamic responses (balance amounts, scores) are generated on-the-fly; all financial backends are mocked via JSON files; call state is tracked per CallSid in an in-memory dict.

**Tech Stack:** Python 3.11, Flask, Twilio, Sarvam AI (TTS + STT), pytest, python-dotenv, requests, ngrok (local tunnel)

---

## File Map

| File | Responsibility |
|------|---------------|
| `app.py` | All Twilio webhook routes + Flask app entry point |
| `config.py` | Language config, prompt names, env var loading |
| `mock_db.py` | Load/save users.json, accounts.json, transactions.json |
| `services/sarvam_tts.py` | Sarvam AI TTS API wrapper → returns MP3 bytes |
| `services/credit_score.py` | Behavioral credit score calculation (300–900) |
| `services/financial_ops.py` | Mock UPI, loan, insurance, savings, PF/NPS operations |
| `generate_prompts.py` | One-time script: generate all static prompt MP3s |
| `data/users.json` | User profiles (phone → name, mPIN, UPI ID, account) |
| `data/accounts.json` | Account balances (account_id → balance, FD, PF, NPS) |
| `data/transactions.json` | Transaction history per phone (for credit scoring) |
| `prompt_audio/` | Pre-generated static MP3 files `{lang}_{prompt}.mp3` |
| `requirements.txt` | All Python dependencies |
| `.env.example` | Template for environment variables |

---

## Task 1: Project Skeleton + Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `config.py`

- [ ] **Step 1: Write requirements.txt**

```
flask==3.0.3
twilio==9.3.2
requests==2.32.3
python-dotenv==1.0.1
pytest==8.2.2
```

- [ ] **Step 2: Write .env.example**

```
SARVAM_API_KEY=your_sarvam_api_key_here
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890
SERVER_BASE_URL=https://your-ngrok-url.ngrok.io
```

- [ ] **Step 3: Write config.py**

```python
import os
from dotenv import load_dotenv
load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "")

# Maps DTMF digit → language config
LANG_CONFIG = {
    "1": {"lang_key": "hi", "tts_lang": "hi-IN", "name": "Hindi"},
    "2": {"lang_key": "en", "tts_lang": "en-IN", "name": "English"},
    "3": {"lang_key": "ta", "tts_lang": "ta-IN", "name": "Tamil"},
    "4": {"lang_key": "te", "tts_lang": "te-IN", "name": "Telugu"},
    "5": {"lang_key": "kn", "tts_lang": "kn-IN", "name": "Kannada"},
    "6": {"lang_key": "ml", "tts_lang": "ml-IN", "name": "Malayalam"},
    "7": {"lang_key": "mr", "tts_lang": "mr-IN", "name": "Marathi"},
    "8": {"lang_key": "bn", "tts_lang": "bn-IN", "name": "Bengali"},
    "9": {"lang_key": "gu", "tts_lang": "gu-IN", "name": "Gujarati"},
}

# All static audio prompt keys (one MP3 per lang per key)
STATIC_PROMPTS = {
    "hi": {
        "lang_menu":      "हिंदी के लिए 1 दबाएं, English के लिए 2 दबाएं, Tamil के लिए 3 दबाएं, Telugu के लिए 4 दबाएं, Kannada के लिए 5 दबाएं, Malayalam के लिए 6 दबाएं, Marathi के लिए 7 दबाएं, Bengali के लिए 8 दबाएं, Gujarati के लिए 9 दबाएं।",
        "enter_phone":    "कृपया अपना 10 अंकों का मोबाइल नंबर दर्ज करें।",
        "enter_mpin":     "कृपया अपना 4 अंकों का mPIN दर्ज करें।",
        "wrong_mpin":     "गलत mPIN। कृपया पुनः प्रयास करें।",
        "mpin_locked":    "बहुत अधिक गलत प्रयास। कॉल समाप्त हो रही है।",
        "no_account":     "इस नंबर पर कोई खाता नहीं मिला। धन्यवाद।",
        "main_menu":      "मुख्य मेनू। UPI भुगतान के लिए 1 दबाएं। बैलेंस देखने के लिए 2 दबाएं। लोन के लिए 3 दबाएं। बीमा के लिए 4 दबाएं। क्रेडिट स्कोर के लिए 5 दबाएं। बचत के लिए 6 दबाएं। PF या NPS बैलेंस के लिए 7 दबाएं।",
        "upi_ask_recipient": "कृपया प्राप्तकर्ता का 10 अंकों का मोबाइल नंबर दर्ज करें।",
        "upi_ask_amount": "कृपया राशि दर्ज करें, फिर # दबाएं।",
        "upi_confirm":    "भुगतान की पुष्टि करने के लिए 1 दबाएं, रद्द करने के लिए 2 दबाएं।",
        "upi_success":    "भुगतान सफल रहा।",
        "upi_failed":     "भुगतान विफल। कृपया पुनः प्रयास करें।",
        "upi_not_found":  "प्राप्तकर्ता का खाता नहीं मिला।",
        "loan_not_eligible": "खेद है, आपका क्रेडिट स्कोर 400 से कम है। आप लोन के लिए पात्र नहीं हैं।",
        "loan_ask_amount": "आप अधिकतम 25000 रुपये तक का लोन ले सकते हैं। कृपया राशि दर्ज करें, फिर # दबाएं।",
        "loan_confirm":   "लोन की पुष्टि के लिए 1 दबाएं, रद्द करने के लिए 2 दबाएं।",
        "loan_approved":  "लोन स्वीकृत। राशि आपके खाते में जमा कर दी जाएगी।",
        "loan_rejected":  "आपकी पात्रता के आधार पर लोन अस्वीकृत।",
        "insurance_menu": "बीमा प्रकार चुनें। स्वास्थ्य बीमा के लिए 1 दबाएं। दुर्घटना बीमा के लिए 2 दबाएं। फसल बीमा के लिए 3 दबाएं।",
        "insurance_confirm": "बीमा सक्रिय करने के लिए 1 दबाएं, रद्द के लिए 2 दबाएं।",
        "insurance_success": "बीमा सफलतापूर्वक सक्रिय।",
        "savings_menu":   "बचत विकल्प। सावधि जमा के लिए 1 दबाएं। आवर्ती जमा के लिए 2 दबाएं।",
        "savings_ask_amount": "कृपया जमा राशि दर्ज करें, फिर # दबाएं।",
        "savings_ask_duration": "अवधि महीनों में दर्ज करें, फिर # दबाएं।",
        "savings_confirm": "जमा की पुष्टि के लिए 1 दबाएं।",
        "savings_success": "जमा सफलतापूर्वक दर्ज।",
        "invalid":        "अमान्य इनपुट। कृपया पुनः प्रयास करें।",
        "goodbye":        "VaaniPay का उपयोग करने के लिए धन्यवाद। नमस्ते।",
        "error":          "तकनीकी समस्या। कृपया बाद में प्रयास करें।",
        "please_wait":    "कृपया प्रतीक्षा करें।",
        "auth_success":   "प्रमाणीकरण सफल। VaaniPay में आपका स्वागत है।",
    },
    "en": {
        "lang_menu":      "Press 1 for Hindi, 2 for English, 3 for Tamil, 4 for Telugu, 5 for Kannada, 6 for Malayalam, 7 for Marathi, 8 for Bengali, 9 for Gujarati.",
        "enter_phone":    "Please enter your 10-digit mobile number.",
        "enter_mpin":     "Please enter your 4-digit mPIN.",
        "wrong_mpin":     "Incorrect mPIN. Please try again.",
        "mpin_locked":    "Too many failed attempts. Ending call.",
        "no_account":     "No account found for this number. Thank you.",
        "main_menu":      "Main menu. Press 1 for UPI payment. Press 2 for balance. Press 3 for loan. Press 4 for insurance. Press 5 for credit score. Press 6 for savings. Press 7 for PF or NPS balance.",
        "upi_ask_recipient": "Please enter the recipient's 10-digit mobile number.",
        "upi_ask_amount": "Please enter the amount, then press hash.",
        "upi_confirm":    "Press 1 to confirm payment, 2 to cancel.",
        "upi_success":    "Payment successful.",
        "upi_failed":     "Payment failed. Please try again.",
        "upi_not_found":  "Recipient account not found.",
        "loan_not_eligible": "Sorry, your credit score is below 400. You are not eligible for a loan.",
        "loan_ask_amount": "You can borrow up to 25000 rupees. Please enter the amount, then press hash.",
        "loan_confirm":   "Press 1 to confirm loan, 2 to cancel.",
        "loan_approved":  "Loan approved. Amount will be credited to your account.",
        "loan_rejected":  "Loan rejected based on your eligibility.",
        "insurance_menu": "Choose insurance type. Press 1 for health insurance. Press 2 for accident insurance. Press 3 for crop insurance.",
        "insurance_confirm": "Press 1 to activate insurance, 2 to cancel.",
        "insurance_success": "Insurance activated successfully.",
        "savings_menu":   "Savings options. Press 1 for Fixed Deposit. Press 2 for Recurring Deposit.",
        "savings_ask_amount": "Please enter the deposit amount, then press hash.",
        "savings_ask_duration": "Enter duration in months, then press hash.",
        "savings_confirm": "Press 1 to confirm deposit.",
        "savings_success": "Deposit recorded successfully.",
        "invalid":        "Invalid input. Please try again.",
        "goodbye":        "Thank you for using VaaniPay. Goodbye.",
        "error":          "Technical error. Please try again later.",
        "please_wait":    "Please wait.",
        "auth_success":   "Authentication successful. Welcome to VaaniPay.",
    },
    "ta": {
        "lang_menu":      "தமிழுக்கு 3 அழுத்தவும்.",
        "enter_phone":    "உங்கள் 10 இலக்க மொபைல் எண்ணை உள்ளிடவும்.",
        "enter_mpin":     "உங்கள் 4 இலக்க mPIN ஐ உள்ளிடவும்.",
        "wrong_mpin":     "தவறான mPIN. மீண்டும் முயற்சிக்கவும்.",
        "mpin_locked":    "அதிக தோல்வி முயற்சிகள். அழைப்பு நிறுத்தப்படுகிறது.",
        "no_account":     "இந்த எண்ணில் கணக்கு இல்லை.",
        "main_menu":      "முக்கிய மெனு. UPI பணம் செலுத்த 1. இருப்பு 2. கடன் 3. காப்பீடு 4. கிரெடிட் ஸ்கோர் 5. சேமிப்பு 6. PF அல்லது NPS இருப்பு 7.",
        "upi_ask_recipient": "பெறுநரின் 10 இலக்க மொபைல் எண்ணை உள்ளிடவும்.",
        "upi_ask_amount": "தொகையை உள்ளிட்டு # அழுத்தவும்.",
        "upi_confirm":    "உறுதிப்படுத்த 1, ரத்து செய்ய 2.",
        "upi_success":    "பணம் செலுத்துதல் வெற்றிகரமாக நடைபெற்றது.",
        "upi_failed":     "பணம் செலுத்துதல் தோல்வி.",
        "upi_not_found":  "பெறுநர் கணக்கு இல்லை.",
        "loan_not_eligible": "மன்னிக்கவும், உங்கள் கிரெடிட் ஸ்கோர் குறைவாக உள்ளது.",
        "loan_ask_amount": "25000 ரூபாய் வரை கடன் பெறலாம். தொகை உள்ளிட்டு # அழுத்தவும்.",
        "loan_confirm":   "கடன் உறுதிப்படுத்த 1, ரத்து 2.",
        "loan_approved":  "கடன் அனுமதிக்கப்பட்டது.",
        "loan_rejected":  "கடன் நிராகரிக்கப்பட்டது.",
        "insurance_menu": "காப்பீடு வகை. 1 சுகாதார, 2 விபத்து, 3 பயிர்.",
        "insurance_confirm": "காப்பீடு செயல்படுத்த 1, ரத்து 2.",
        "insurance_success": "காப்பீடு செயல்படுத்தப்பட்டது.",
        "savings_menu":   "சேமிப்பு விருப்பங்கள். 1 நிலையான வைப்பு, 2 தொடர் வைப்பு.",
        "savings_ask_amount": "தொகை உள்ளிட்டு # அழுத்தவும்.",
        "savings_ask_duration": "மாதங்களில் காலம் உள்ளிட்டு # அழுத்தவும்.",
        "savings_confirm": "உறுதிப்படுத்த 1.",
        "savings_success": "வைப்பு பதிவு செய்யப்பட்டது.",
        "invalid":        "தவறான உள்ளீடு.",
        "goodbye":        "VaaniPay பயன்படுத்தியதற்கு நன்றி.",
        "error":          "தொழில்நுட்ப பிழை.",
        "please_wait":    "தயவுசெய்து காத்திருங்கள்.",
        "auth_success":   "அங்கீகாரம் வெற்றிகரமானது.",
    },
    "te": {
        "lang_menu":      "తెలుగు కోసం 4 నొక్కండి.",
        "enter_phone":    "మీ 10 అంకెల మొబైల్ నంబర్ నమోదు చేయండి.",
        "enter_mpin":     "మీ 4 అంకెల mPIN నమోదు చేయండి.",
        "wrong_mpin":     "తప్పు mPIN. మళ్ళీ ప్రయత్నించండి.",
        "mpin_locked":    "ఎక్కువ విఫల ప్రయత్నాలు. కాల్ ముగుస్తోంది.",
        "no_account":     "ఈ నంబర్‌కు ఖాతా లేదు.",
        "main_menu":      "ప్రధాన మెనూ. UPI చెల్లింపు 1. బ్యాలెన్స్ 2. రుణం 3. బీమా 4. క్రెడిట్ స్కోర్ 5. పొదుపులు 6. PF లేదా NPS 7.",
        "upi_ask_recipient": "గ్రహీత 10 అంకెల నంబర్ నమోదు చేయండి.",
        "upi_ask_amount": "మొత్తం నమోదు చేసి # నొక్కండి.",
        "upi_confirm":    "నిర్ధారించేందుకు 1, రద్దుకు 2.",
        "upi_success":    "చెల్లింపు విజయవంతమైంది.",
        "upi_failed":     "చెల్లింపు విఫలమైంది.",
        "upi_not_found":  "గ్రహీత ఖాతా కనుగొనబడలేదు.",
        "loan_not_eligible": "క్షమించండి, మీరు రుణానికి అర్హులు కాదు.",
        "loan_ask_amount": "25000 వరకు రుణం పొందవచ్చు. మొత్తం నమోదు చేసి # నొక్కండి.",
        "loan_confirm":   "రుణం నిర్ధారించేందుకు 1, రద్దుకు 2.",
        "loan_approved":  "రుణం మంజూరైంది.",
        "loan_rejected":  "రుణం తిరస్కరించబడింది.",
        "insurance_menu": "బీమా రకం. 1 ఆరోగ్యం, 2 ప్రమాదం, 3 పంట.",
        "insurance_confirm": "బీమా చేతికి 1, రద్దుకు 2.",
        "insurance_success": "బీమా సక్రియం అయింది.",
        "savings_menu":   "పొదుపు ఎంపికలు. 1 స్థిర డిపాజిట్, 2 పునరావృత డిపాజిట్.",
        "savings_ask_amount": "మొత్తం నమోదు చేసి # నొక్కండి.",
        "savings_ask_duration": "నెలల్లో వ్యవధి నమోదు చేసి # నొక్కండి.",
        "savings_confirm": "నిర్ధారించేందుకు 1.",
        "savings_success": "డిపాజిట్ నమోదైంది.",
        "invalid":        "చెల్లని ఇన్‌పుట్.",
        "goodbye":        "VaaniPay ఉపయోగించినందుకు ధన్యవాదాలు.",
        "error":          "సాంకేతిక లోపం.",
        "please_wait":    "దయచేసి వేచి ఉండండి.",
        "auth_success":   "ప్రమాణీకరణ విజయవంతమైంది.",
    },
    "kn": {
        "lang_menu":      "ಕನ್ನಡಕ್ಕಾಗಿ 5 ಒತ್ತಿರಿ.",
        "enter_phone":    "ನಿಮ್ಮ 10 ಅಂಕಿಯ ಮೊಬೈಲ್ ಸಂಖ್ಯೆ ನಮೂದಿಸಿ.",
        "enter_mpin":     "ನಿಮ್ಮ 4 ಅಂಕಿಯ mPIN ನಮೂದಿಸಿ.",
        "wrong_mpin":     "ತಪ್ಪು mPIN. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
        "mpin_locked":    "ಹಲವು ತಪ್ಪು ಪ್ರಯತ್ನಗಳು. ಕರೆ ಕೊನೆಗೊಳ್ಳುತ್ತಿದೆ.",
        "no_account":     "ಈ ಸಂಖ್ಯೆಗೆ ಖಾತೆ ಇಲ್ಲ.",
        "main_menu":      "ಮುಖ್ಯ ಮೆನು. UPI ಪಾವತಿ 1. ಶಿಲ್ಕು 2. ಸಾಲ 3. ವಿಮೆ 4. ಕ್ರೆಡಿಟ್ ಸ್ಕೋರ್ 5. ಉಳಿತಾಯ 6. PF ಅಥವಾ NPS 7.",
        "upi_ask_recipient": "ಸ್ವೀಕರಿಸುವವರ 10 ಅಂಕಿಯ ಸಂಖ್ಯೆ ನಮೂದಿಸಿ.",
        "upi_ask_amount": "ಮೊತ್ತ ನಮೂದಿಸಿ, # ಒತ್ತಿರಿ.",
        "upi_confirm":    "ದೃಢೀಕರಿಸಲು 1, ರದ್ದು 2.",
        "upi_success":    "ಪಾವತಿ ಯಶಸ್ವಿ.",
        "upi_failed":     "ಪಾವತಿ ವಿಫಲ.",
        "upi_not_found":  "ಸ್ವೀಕರಿಸುವವರ ಖಾತೆ ಇಲ್ಲ.",
        "loan_not_eligible": "ಕ್ಷಮಿಸಿ, ನೀವು ಸಾಲಕ್ಕೆ ಅರ್ಹರಲ್ಲ.",
        "loan_ask_amount": "25000 ರೂಪಾಯಿ ವರೆಗೆ ಸಾಲ. ಮೊತ್ತ ನಮೂದಿಸಿ, # ಒತ್ತಿರಿ.",
        "loan_confirm":   "ಸಾಲ ದೃಢೀಕರಿಸಲು 1, ರದ್ದು 2.",
        "loan_approved":  "ಸಾಲ ಅನುಮೋದಿತ.",
        "loan_rejected":  "ಸಾಲ ತಿರಸ್ಕೃತ.",
        "insurance_menu": "ವಿಮೆ ಪ್ರಕಾರ. 1 ಆರೋಗ್ಯ, 2 ಅಪಘಾತ, 3 ಬೆಳೆ.",
        "insurance_confirm": "ವಿಮೆ ಸಕ್ರಿಯ 1, ರದ್ದು 2.",
        "insurance_success": "ವಿಮೆ ಸಕ್ರಿಯಗೊಂಡಿದೆ.",
        "savings_menu":   "ಉಳಿತಾಯ. 1 ಸ್ಥಿರ ಠೇವಣಿ, 2 ಆವರ್ತಿ ಠೇವಣಿ.",
        "savings_ask_amount": "ಮೊತ್ತ ನಮೂದಿಸಿ, # ಒತ್ತಿರಿ.",
        "savings_ask_duration": "ತಿಂಗಳ ಅವಧಿ ನಮೂದಿಸಿ, # ಒತ್ತಿರಿ.",
        "savings_confirm": "ದೃಢೀಕರಿಸಲು 1.",
        "savings_success": "ಠೇವಣಿ ದಾಖಲಾಯಿತು.",
        "invalid":        "ಅಮಾನ್ಯ ಇನ್‌ಪುಟ್.",
        "goodbye":        "VaaniPay ಬಳಸಿದ್ದಕ್ಕಾಗಿ ಧನ್ಯವಾದ.",
        "error":          "ತಾಂತ್ರಿಕ ದೋಷ.",
        "please_wait":    "ದಯವಿಟ್ಟು ನಿರೀಕ್ಷಿಸಿ.",
        "auth_success":   "ದೃಢೀಕರಣ ಯಶಸ್ವಿ.",
    },
    "ml": {
        "lang_menu":      "മലയാളത്തിന് 6 അമർത്തുക.",
        "enter_phone":    "നിങ്ങളുടെ 10 അക്ക മൊബൈൽ നമ്പർ നൽകുക.",
        "enter_mpin":     "നിങ്ങളുടെ 4 അക്ക mPIN നൽകുക.",
        "wrong_mpin":     "തെറ്റായ mPIN. വീണ്ടും ശ്രമിക്കുക.",
        "mpin_locked":    "പരാജയ ശ്രമങ്ങൾ അധികമായി. കോൾ അവസാനിക്കുന്നു.",
        "no_account":     "ഈ നമ്പറിൽ അക്കൗണ്ട് ഇല്ല.",
        "main_menu":      "ഗ്ലോബൽ മെനു. UPI പേയ്‌മെന്റ് 1. ബാലൻസ് 2. ലോൺ 3. ഇൻഷൂറൻസ് 4. ക്രെഡിറ്റ് സ്‌കോർ 5. സേവിങ്‌സ് 6. PF അല്ലെങ്കിൽ NPS 7.",
        "upi_ask_recipient": "സ്വീകർത്താവിന്റെ 10 അക്ക നമ്പർ നൽകുക.",
        "upi_ask_amount": "തുക നൽകി # അമർത്തുക.",
        "upi_confirm":    "സ്ഥിരീകരിക്കാൻ 1, റദ്ദ് ചെയ്യാൻ 2.",
        "upi_success":    "പേയ്‌മെന്റ് വിജയകരം.",
        "upi_failed":     "പേയ്‌മെന്റ് പരാജയം.",
        "upi_not_found":  "സ്വീകർത്താവിന്റെ അക്കൗണ്ട് ഇല്ല.",
        "loan_not_eligible": "ക്ഷമിക്കുക, നിങ്ങൾ ലോണിന് അർഹരല്ല.",
        "loan_ask_amount": "25000 രൂപ വരെ ലോൺ. തുക നൽകി # അമർത്തുക.",
        "loan_confirm":   "ലോൺ സ്ഥിരീകരിക്കാൻ 1, റദ്ദ് 2.",
        "loan_approved":  "ലോൺ അനുവദിച്ചു.",
        "loan_rejected":  "ലോൺ നിരസിച്ചു.",
        "insurance_menu": "ഇൻഷൂറൻസ് തരം. 1 ആരോഗ്യം, 2 അപകടം, 3 വിള.",
        "insurance_confirm": "ഇൻഷൂറൻസ് സജീവമാക്കാൻ 1, റദ്ദ് 2.",
        "insurance_success": "ഇൻഷൂറൻസ് സജീവമായി.",
        "savings_menu":   "സേവിങ്‌സ്. 1 ഫിക്‌സഡ് ഡിപ്പോസിറ്റ്, 2 റിക്കറിങ് ഡിപ്പോസിറ്റ്.",
        "savings_ask_amount": "തുക നൽകി # അമർത്തുക.",
        "savings_ask_duration": "മാസങ്ങളിൽ കാലാവധി നൽകി # അമർത്തുക.",
        "savings_confirm": "സ്ഥിരീകരിക്കാൻ 1.",
        "savings_success": "ഡിപ്പോസിറ്റ് രേഖപ്പെടുത്തി.",
        "invalid":        "അസാധുവായ ഇൻപുട്ട്.",
        "goodbye":        "VaaniPay ഉപയോഗിച്ചതിന് നന്ദി.",
        "error":          "സാങ്കേതിക പിഴവ്.",
        "please_wait":    "ദയവായി കാത്തിരിക്കുക.",
        "auth_success":   "പ്രാമാണീകരണം വിജയകരം.",
    },
    "mr": {
        "lang_menu":      "मराठीसाठी 7 दाबा.",
        "enter_phone":    "कृपया तुमचा 10 अंकी मोबाइल नंबर प्रविष्ट करा.",
        "enter_mpin":     "कृपया तुमचा 4 अंकी mPIN प्रविष्ट करा.",
        "wrong_mpin":     "चुकीचा mPIN. पुन्हा प्रयत्न करा.",
        "mpin_locked":    "जास्त चुकीचे प्रयत्न. कॉल संपत आहे.",
        "no_account":     "या नंबरवर खाते आढळले नाही.",
        "main_menu":      "मुख्य मेनू. UPI देयकासाठी 1. शिल्लकसाठी 2. कर्जासाठी 3. विम्यासाठी 4. क्रेडिट स्कोरसाठी 5. बचतीसाठी 6. PF किंवा NPS साठी 7.",
        "upi_ask_recipient": "प्राप्तकर्त्याचा 10 अंकी नंबर प्रविष्ट करा.",
        "upi_ask_amount": "रक्कम प्रविष्ट करा, मग # दाबा.",
        "upi_confirm":    "देयक पुष्टी करण्यासाठी 1, रद्द करण्यासाठी 2.",
        "upi_success":    "देयक यशस्वी.",
        "upi_failed":     "देयक अयशस्वी.",
        "upi_not_found":  "प्राप्तकर्त्याचे खाते आढळले नाही.",
        "loan_not_eligible": "माफ करा, तुम्ही कर्जासाठी पात्र नाही.",
        "loan_ask_amount": "25000 पर्यंत कर्ज मिळवता येईल. रक्कम प्रविष्ट करा, # दाबा.",
        "loan_confirm":   "कर्ज पुष्टी 1, रद्द 2.",
        "loan_approved":  "कर्ज मंजूर.",
        "loan_rejected":  "कर्ज नाकारले.",
        "insurance_menu": "विमा प्रकार. 1 आरोग्य, 2 अपघात, 3 पीक.",
        "insurance_confirm": "विमा सक्रिय करण्यासाठी 1, रद्द 2.",
        "insurance_success": "विमा यशस्वीरित्या सक्रिय.",
        "savings_menu":   "बचत पर्याय. 1 मुदत ठेव, 2 आवर्ती ठेव.",
        "savings_ask_amount": "रक्कम प्रविष्ट करा, # दाबा.",
        "savings_ask_duration": "महिन्यांत कालावधी प्रविष्ट करा, # दाबा.",
        "savings_confirm": "पुष्टीसाठी 1.",
        "savings_success": "ठेव नोंदवली.",
        "invalid":        "अवैध इनपुट.",
        "goodbye":        "VaaniPay वापरल्याबद्दल धन्यवाद.",
        "error":          "तांत्रिक समस्या.",
        "please_wait":    "कृपया प्रतीक्षा करा.",
        "auth_success":   "प्रमाणीकरण यशस्वी.",
    },
    "bn": {
        "lang_menu":      "বাংলার জন্য 8 চাপুন।",
        "enter_phone":    "আপনার 10 সংখ্যার মোবাইল নম্বর লিখুন।",
        "enter_mpin":     "আপনার 4 সংখ্যার mPIN লিখুন।",
        "wrong_mpin":     "ভুল mPIN। আবার চেষ্টা করুন।",
        "mpin_locked":    "অনেক ভুল চেষ্টা। কল শেষ হচ্ছে।",
        "no_account":     "এই নম্বরে কোনো অ্যাকাউন্ট পাওয়া যায়নি।",
        "main_menu":      "প্রধান মেনু। UPI পেমেন্ট 1। ব্যালেন্স 2। ঋণ 3। বীমা 4। ক্রেডিট স্কোর 5। সঞ্চয় 6। PF বা NPS 7।",
        "upi_ask_recipient": "প্রাপকের 10 সংখ্যার নম্বর লিখুন।",
        "upi_ask_amount": "পরিমাণ লিখুন, তারপর # চাপুন।",
        "upi_confirm":    "নিশ্চিত করতে 1, বাতিল 2।",
        "upi_success":    "পেমেন্ট সফল।",
        "upi_failed":     "পেমেন্ট ব্যর্থ।",
        "upi_not_found":  "প্রাপকের অ্যাকাউন্ট পাওয়া যায়নি।",
        "loan_not_eligible": "দুঃখিত, আপনি ঋণের যোগ্য নন।",
        "loan_ask_amount": "25000 পর্যন্ত ঋণ পেতে পারেন। পরিমাণ লিখুন, # চাপুন।",
        "loan_confirm":   "ঋণ নিশ্চিত 1, বাতিল 2।",
        "loan_approved":  "ঋণ অনুমোদিত।",
        "loan_rejected":  "ঋণ প্রত্যাখ্যাত।",
        "insurance_menu": "বীমার ধরন। 1 স্বাস্থ্য, 2 দুর্ঘটনা, 3 ফসল।",
        "insurance_confirm": "বীমা সক্রিয় করতে 1, বাতিল 2।",
        "insurance_success": "বীমা সফলভাবে সক্রিয়।",
        "savings_menu":   "সঞ্চয়। 1 স্থায়ী আমানত, 2 পুনরাবৃত্তি আমানত।",
        "savings_ask_amount": "পরিমাণ লিখুন, # চাপুন।",
        "savings_ask_duration": "মাসে মেয়াদ লিখুন, # চাপুন।",
        "savings_confirm": "নিশ্চিত করতে 1।",
        "savings_success": "আমানত নথিভুক্ত।",
        "invalid":        "অবৈধ ইনপুট।",
        "goodbye":        "VaaniPay ব্যবহারের জন্য ধন্যবাদ।",
        "error":          "প্রযুক্তিগত ত্রুটি।",
        "please_wait":    "অনুগ্রহ করে অপেক্ষা করুন।",
        "auth_success":   "প্রমাণীকরণ সফল।",
    },
    "gu": {
        "lang_menu":      "ગુજરાતી માટે 9 દબાવો.",
        "enter_phone":    "કૃપા કરીને તમારો 10 અંકનો મોબાઈલ નંબર દાખલ કરો.",
        "enter_mpin":     "કૃપા કરીને તમારો 4 અંકનો mPIN દાખલ કરો.",
        "wrong_mpin":     "ખોટો mPIN. ફરી પ્રયાસ કરો.",
        "mpin_locked":    "ઘણા ખોટા પ્રયાસ. કૉલ સમાપ્ત.",
        "no_account":     "આ નંબર પર ખાતું મળ્યું નહીં.",
        "main_menu":      "મુખ્ય મેનૂ. UPI ચૂકવણી 1. બૅલૅન્સ 2. લોન 3. વીમો 4. ક્રેડિટ સ્કોર 5. બચત 6. PF અથવા NPS 7.",
        "upi_ask_recipient": "પ્રાપ્તકર્તાનો 10 અંકનો નંબર દાખલ કરો.",
        "upi_ask_amount": "રકમ દાખલ કરો, # દબાવો.",
        "upi_confirm":    "ચૂકવણી પ્રમાણિત 1, રદ 2.",
        "upi_success":    "ચૂકવણી સફળ.",
        "upi_failed":     "ચૂકવણી નિષ્ફળ.",
        "upi_not_found":  "પ્રાપ્તકર્તાનું ખાતું મળ્યું નહીં.",
        "loan_not_eligible": "માફ કરશો, તમે લોન માટે પાત્ર નથી.",
        "loan_ask_amount": "25000 સુધી લોન. રકમ દાખલ કરો, # દબાવો.",
        "loan_confirm":   "લોન પ્રમાણિત 1, રદ 2.",
        "loan_approved":  "લોન મંજૂર.",
        "loan_rejected":  "લોન નકારાઈ.",
        "insurance_menu": "વીમો. 1 સ્વાસ્થ્ય, 2 અકસ્માત, 3 પાક.",
        "insurance_confirm": "વીમો સક્રિય 1, રદ 2.",
        "insurance_success": "વીમો સફળ.",
        "savings_menu":   "બચત. 1 ફિક્સ્ડ ડિપોઝિટ, 2 રિકરિંગ ડિપોઝિટ.",
        "savings_ask_amount": "રકમ દાખલ કરો, # દબાવો.",
        "savings_ask_duration": "મહિનામાં સમયગાળો, # દબાવો.",
        "savings_confirm": "પ્રમાણિત 1.",
        "savings_success": "ડિપોઝિટ નોંધ્યું.",
        "invalid":        "અમાન્ય ઇનપુટ.",
        "goodbye":        "VaaniPay ઉપયોગ બદ્દલ આભાર.",
        "error":          "તકનીકી ભૂલ.",
        "please_wait":    "કૃપા કરી રાહ જુઓ.",
        "auth_success":   "પ્રમાણીકરણ સફળ.",
    },
}
```

- [ ] **Step 4: Install dependencies**

```bash
pip install flask twilio requests python-dotenv pytest
```

Expected output: Successfully installed packages, no errors.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example config.py
git commit -m "feat: project skeleton, language config, and prompt text"
```

---

## Task 2: Mock Database Setup

**Files:**
- Create: `data/users.json`
- Create: `data/accounts.json`
- Create: `data/transactions.json`
- Create: `mock_db.py`

- [ ] **Step 1: Create data/users.json**

```json
{
  "9876543210": {
    "name": "Ramesh Kumar",
    "mpin": "1234",
    "upi_id": "ramesh@vaani",
    "account_id": "ACC001",
    "lang_key": "hi",
    "insurance_active": [],
    "loan_active": false,
    "loan_outstanding": 0,
    "referral_count": 3
  },
  "8765432109": {
    "name": "Priya Devi",
    "mpin": "5678",
    "upi_id": "priya@vaani",
    "account_id": "ACC002",
    "lang_key": "ta",
    "insurance_active": ["health"],
    "loan_active": false,
    "loan_outstanding": 0,
    "referral_count": 1
  },
  "7654321098": {
    "name": "Suresh Babu",
    "mpin": "9012",
    "upi_id": "suresh@vaani",
    "account_id": "ACC003",
    "lang_key": "te",
    "insurance_active": [],
    "loan_active": true,
    "loan_outstanding": 5000,
    "referral_count": 5
  }
}
```

- [ ] **Step 2: Create data/accounts.json**

```json
{
  "ACC001": {
    "balance": 15000.00,
    "fd_balance": 5000.00,
    "fd_duration_months": 12,
    "fd_interest_rate": 6.5,
    "rd_monthly": 500.00,
    "pf_balance": 120000.00,
    "nps_balance": 45000.00
  },
  "ACC002": {
    "balance": 8200.50,
    "fd_balance": 0,
    "fd_duration_months": 0,
    "fd_interest_rate": 0,
    "rd_monthly": 200.00,
    "pf_balance": 0,
    "nps_balance": 22000.00
  },
  "ACC003": {
    "balance": 3500.00,
    "fd_balance": 10000.00,
    "fd_duration_months": 6,
    "fd_interest_rate": 7.0,
    "rd_monthly": 0,
    "pf_balance": 85000.00,
    "nps_balance": 0
  }
}
```

- [ ] **Step 3: Create data/transactions.json**

```json
{
  "9876543210": [
    {"date": "2026-04-10", "type": "send", "amount": 500, "status": "success"},
    {"date": "2026-04-05", "type": "receive", "amount": 2000, "status": "success"},
    {"date": "2026-03-28", "type": "send", "amount": 300, "status": "success"},
    {"date": "2026-03-20", "type": "send", "amount": 1500, "status": "success"},
    {"date": "2026-03-15", "type": "receive", "amount": 5000, "status": "success"},
    {"date": "2026-03-10", "type": "send", "amount": 200, "status": "success"},
    {"date": "2026-03-01", "type": "loan_repayment", "amount": 1000, "status": "success"},
    {"date": "2026-02-20", "type": "send", "amount": 800, "status": "success"},
    {"date": "2026-02-10", "type": "receive", "amount": 3000, "status": "success"},
    {"date": "2026-02-01", "type": "loan_repayment", "amount": 1000, "status": "success"}
  ],
  "8765432109": [
    {"date": "2026-04-08", "type": "send", "amount": 200, "status": "success"},
    {"date": "2026-04-01", "type": "send", "amount": 150, "status": "success"},
    {"date": "2026-03-15", "type": "receive", "amount": 1000, "status": "success"}
  ],
  "7654321098": [
    {"date": "2026-04-11", "type": "send", "amount": 1000, "status": "success"},
    {"date": "2026-04-03", "type": "loan_repayment", "amount": 2000, "status": "success"},
    {"date": "2026-03-25", "type": "send", "amount": 500, "status": "success"},
    {"date": "2026-03-20", "type": "receive", "amount": 4000, "status": "success"},
    {"date": "2026-03-10", "type": "send", "amount": 700, "status": "success"},
    {"date": "2026-03-03", "type": "loan_repayment", "amount": 2000, "status": "success"},
    {"date": "2026-02-25", "type": "send", "amount": 300, "status": "success"},
    {"date": "2026-02-15", "type": "send", "amount": 900, "status": "success"},
    {"date": "2026-02-03", "type": "loan_repayment", "amount": 2000, "status": "success"},
    {"date": "2026-01-25", "type": "receive", "amount": 6000, "status": "success"},
    {"date": "2026-01-10", "type": "send", "amount": 1100, "status": "success"},
    {"date": "2026-01-03", "type": "loan_repayment", "amount": 2000, "status": "success"}
  ]
}
```

- [ ] **Step 4: Write mock_db.py**

```python
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def _load(filename: str) -> dict:
    path = DATA_DIR / filename
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(filename: str, data: dict):
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_user(phone: str) -> dict | None:
    users = _load("users.json")
    return users.get(phone)


def get_account(account_id: str) -> dict | None:
    accounts = _load("accounts.json")
    return accounts.get(account_id)


def get_transactions(phone: str) -> list:
    txns = _load("transactions.json")
    return txns.get(phone, [])


def update_account_balance(account_id: str, delta: float):
    accounts = _load("accounts.json")
    if account_id in accounts:
        accounts[account_id]["balance"] = round(
            accounts[account_id]["balance"] + delta, 2
        )
    _save("accounts.json", accounts)


def add_transaction(phone: str, txn: dict):
    txns = _load("transactions.json")
    if phone not in txns:
        txns[phone] = []
    txns[phone].insert(0, txn)
    _save("transactions.json", txns)


def update_user(phone: str, fields: dict):
    users = _load("users.json")
    if phone in users:
        users[phone].update(fields)
    _save("users.json", users)


def update_account(account_id: str, fields: dict):
    accounts = _load("accounts.json")
    if account_id in accounts:
        accounts[account_id].update(fields)
    _save("accounts.json", accounts)
```

- [ ] **Step 5: Run a quick sanity check**

```python
# Run in python REPL: python -c "from mock_db import get_user; print(get_user('9876543210'))"
```

Expected output: `{'name': 'Ramesh Kumar', 'mpin': '1234', ...}`

- [ ] **Step 6: Commit**

```bash
git add data/ mock_db.py
git commit -m "feat: mock database for users, accounts, and transactions"
```

---

## Task 3: Sarvam AI TTS Client

**Files:**
- Create: `services/sarvam_tts.py`
- Create: `services/__init__.py`

- [ ] **Step 1: Create services/__init__.py** (empty file)

```python
```

- [ ] **Step 2: Write services/sarvam_tts.py**

```python
import base64
import os
from pathlib import Path
import requests
from config import SARVAM_API_KEY

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"

# Maps lang_key → Sarvam TTS language code + speaker
LANG_TTS_CONFIG = {
    "hi": {"target_language_code": "hi-IN", "speaker": "meera"},
    "en": {"target_language_code": "en-IN", "speaker": "meera"},
    "ta": {"target_language_code": "ta-IN", "speaker": "meera"},
    "te": {"target_language_code": "te-IN", "speaker": "meera"},
    "kn": {"target_language_code": "kn-IN", "speaker": "meera"},
    "ml": {"target_language_code": "ml-IN", "speaker": "meera"},
    "mr": {"target_language_code": "mr-IN", "speaker": "meera"},
    "bn": {"target_language_code": "bn-IN", "speaker": "meera"},
    "gu": {"target_language_code": "gu-IN", "speaker": "meera"},
}


def generate_tts(text: str, lang_key: str) -> bytes:
    """
    Call Sarvam AI TTS API and return MP3 bytes.
    Falls back to None on error — caller must handle gracefully.
    """
    cfg = LANG_TTS_CONFIG.get(lang_key, LANG_TTS_CONFIG["en"])

    payload = {
        "inputs": [text],
        "target_language_code": cfg["target_language_code"],
        "speaker": cfg["speaker"],
        "pitch": 0,
        "pace": 1.0,
        "loudness": 1.5,
        "speech_sample_rate": 8000,
        "enable_preprocessing": True,
        "model": "bulbul:v1",
    }

    headers = {
        "Content-Type": "application/json",
        "api-subscription-key": SARVAM_API_KEY,
    }

    resp = requests.post(SARVAM_TTS_URL, json=payload, headers=headers, timeout=15)
    resp.raise_for_status()

    data = resp.json()
    audio_b64 = data["audios"][0]
    return base64.b64decode(audio_b64)


def save_tts(text: str, lang_key: str, output_path: Path) -> bool:
    """Generate TTS and save to file. Returns True on success."""
    try:
        audio_bytes = generate_tts(text, lang_key)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)
        return True
    except Exception as e:
        print(f"TTS ERROR [{lang_key}]: {e}")
        return False
```

- [ ] **Step 3: Test TTS client manually**

```bash
# Test: python -c "
# from services.sarvam_tts import generate_tts
# b = generate_tts('नमस्ते, VaaniPay में आपका स्वागत है।', 'hi')
# open('test_hi.mp3','wb').write(b)
# print('saved', len(b), 'bytes')
# "
```

Expected output: `saved XXXXX bytes` (typically 40,000–200,000 bytes for short text)

- [ ] **Step 4: Commit**

```bash
git add services/
git commit -m "feat: Sarvam AI TTS client with multi-language support"
```

---

## Task 4: Static Prompt Generation Script

**Files:**
- Create: `generate_prompts.py`
- Create: `prompt_audio/` (directory, auto-created by script)

- [ ] **Step 1: Write generate_prompts.py**

```python
"""
Run this ONCE to generate all static prompt MP3 files.
Usage: python generate_prompts.py
Output: prompt_audio/{lang}_{prompt}.mp3
"""
from pathlib import Path
from config import STATIC_PROMPTS
from services.sarvam_tts import save_tts

PROMPT_DIR = Path(__file__).parent / "prompt_audio"


def generate_all_prompts():
    total = 0
    failed = 0

    for lang_key, prompts in STATIC_PROMPTS.items():
        print(f"\n--- Generating [{lang_key}] ---")
        for prompt_key, text in prompts.items():
            out_path = PROMPT_DIR / f"{lang_key}_{prompt_key}.mp3"

            if out_path.exists():
                print(f"  SKIP (exists): {out_path.name}")
                total += 1
                continue

            success = save_tts(text, lang_key, out_path)
            total += 1
            if success:
                print(f"  OK: {out_path.name}")
            else:
                failed += 1
                print(f"  FAIL: {out_path.name}")

    print(f"\n=== Done: {total - failed}/{total} prompts generated ===")


if __name__ == "__main__":
    generate_all_prompts()
```

- [ ] **Step 2: Run the generation script**

```bash
python generate_prompts.py
```

Expected output: One `OK: {lang}_{prompt}.mp3` line per prompt (9 langs × ~28 prompts = ~252 files). Failed ones show `FAIL:` — rerun to retry.

- [ ] **Step 3: Verify output**

```bash
ls prompt_audio/ | wc -l
```

Expected: 252 (or close to it, depending on any API failures).

- [ ] **Step 4: Commit**

```bash
git add generate_prompts.py prompt_audio/
git commit -m "feat: static prompt generation script and generated MP3 files"
```

---

## Task 5: Behavioral Credit Scoring Engine

**Files:**
- Create: `services/credit_score.py`
- Test: `tests/test_credit_score.py`

- [ ] **Step 1: Write the failing test**

Create `tests/__init__.py` (empty), then create `tests/test_credit_score.py`:

```python
from services.credit_score import calculate_credit_score


def test_high_activity_user_gets_high_score():
    # User with 12 transactions including 4 loan repayments → high score
    transactions = [
        {"date": "2026-04-10", "type": "send", "amount": 500, "status": "success"},
        {"date": "2026-04-03", "type": "loan_repayment", "amount": 2000, "status": "success"},
        {"date": "2026-03-25", "type": "send", "amount": 500, "status": "success"},
        {"date": "2026-03-20", "type": "receive", "amount": 4000, "status": "success"},
        {"date": "2026-03-10", "type": "send", "amount": 700, "status": "success"},
        {"date": "2026-03-03", "type": "loan_repayment", "amount": 2000, "status": "success"},
        {"date": "2026-02-25", "type": "send", "amount": 300, "status": "success"},
        {"date": "2026-02-15", "type": "send", "amount": 900, "status": "success"},
        {"date": "2026-02-03", "type": "loan_repayment", "amount": 2000, "status": "success"},
        {"date": "2026-01-25", "type": "receive", "amount": 6000, "status": "success"},
        {"date": "2026-01-10", "type": "send", "amount": 1100, "status": "success"},
        {"date": "2026-01-03", "type": "loan_repayment", "amount": 2000, "status": "success"},
    ]
    user = {"referral_count": 5, "loan_active": True, "loan_outstanding": 5000}
    score, factors = calculate_credit_score(transactions, user)
    assert 650 <= score <= 900, f"Expected 650-900, got {score}"
    assert isinstance(factors, list)
    assert len(factors) >= 1


def test_low_activity_user_gets_low_score():
    # User with only 3 transactions → low score
    transactions = [
        {"date": "2026-04-08", "type": "send", "amount": 200, "status": "success"},
        {"date": "2026-04-01", "type": "send", "amount": 150, "status": "success"},
        {"date": "2026-03-15", "type": "receive", "amount": 1000, "status": "success"},
    ]
    user = {"referral_count": 1, "loan_active": False, "loan_outstanding": 0}
    score, factors = calculate_credit_score(transactions, user)
    assert 300 <= score <= 600, f"Expected 300-600, got {score}"


def test_score_within_range():
    # Edge case: empty transactions
    score, factors = calculate_credit_score([], {"referral_count": 0})
    assert 300 <= score <= 900
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_credit_score.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'services.credit_score'`

- [ ] **Step 3: Write services/credit_score.py**

```python
"""
Behavioral credit score on 300–900 scale.

Weights (matching Figure 4 in the spec):
  Transaction Consistency  30%
  Repayment History        25%
  Savings Behavior         20%
  Call Frequency           15%
  Referral Network         10%
"""
from datetime import datetime, timedelta


def calculate_credit_score(transactions: list, user: dict) -> tuple[int, list[str]]:
    """
    Returns (score: int, top_factors: list[str])
    score is in range [300, 900].
    top_factors lists the 2 most impactful positive signals.
    """
    now = datetime.now()
    ninety_days_ago = now - timedelta(days=90)

    # Filter to last 90 days
    recent = []
    for t in transactions:
        try:
            txn_date = datetime.strptime(t["date"], "%Y-%m-%d")
            if txn_date >= ninety_days_ago:
                recent.append(t)
        except Exception:
            pass

    total_txns = len(recent)
    repayments = [t for t in recent if t.get("type") == "loan_repayment"]
    successful = [t for t in recent if t.get("status") == "success"]

    # --- Transaction Consistency (30%) ---
    # 0–20 txns/90d → 0–100 points
    tx_score = min(total_txns / 20, 1.0) * 100

    # --- Repayment History (25%) ---
    # Each on-time repayment = 20 pts, max 100
    repayment_score = min(len(repayments) * 20, 100)

    # --- Savings Behavior (20%) ---
    # Proxy: success rate of transactions
    success_rate = (len(successful) / total_txns) if total_txns > 0 else 0
    savings_score = success_rate * 100

    # --- Call Frequency (15%) ---
    # Total lifetime transactions as proxy
    all_txns = len(transactions)
    call_score = min(all_txns / 15, 1.0) * 100

    # --- Referral Network (10%) ---
    referral_count = user.get("referral_count", 0)
    referral_score = min(referral_count * 10, 100)

    # Weighted composite (0–100)
    composite = (
        tx_score * 0.30
        + repayment_score * 0.25
        + savings_score * 0.20
        + call_score * 0.15
        + referral_score * 0.10
    )

    # Map 0–100 → 300–900
    score = int(300 + composite * 6)
    score = max(300, min(900, score))

    # Determine top factors for user explanation
    component_scores = [
        ("transaction consistency", tx_score),
        ("repayment history", repayment_score),
        ("savings behavior", savings_score),
        ("platform usage", call_score),
        ("referral network", referral_score),
    ]
    component_scores.sort(key=lambda x: x[1], reverse=True)
    top_factors = [name for name, _ in component_scores[:2]]

    return score, top_factors


def get_loan_terms(score: int) -> dict:
    """
    Returns max loan amount and interest rate based on credit score.
    Score <400 → not eligible
    400–549  → ₹500–₹5,000 at 18% p.a.
    550–649  → ₹500–₹10,000 at 15% p.a.
    650–749  → ₹500–₹18,000 at 12% p.a.
    750–900  → ₹500–₹25,000 at 10% p.a.
    """
    if score < 400:
        return {"eligible": False, "max_amount": 0, "interest_rate": 0}
    elif score < 550:
        return {"eligible": True, "max_amount": 5000, "interest_rate": 18}
    elif score < 650:
        return {"eligible": True, "max_amount": 10000, "interest_rate": 15}
    elif score < 750:
        return {"eligible": True, "max_amount": 18000, "interest_rate": 12}
    else:
        return {"eligible": True, "max_amount": 25000, "interest_rate": 10}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_credit_score.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/credit_score.py tests/
git commit -m "feat: behavioral credit scoring engine (300-900 scale)"
```

---

## Task 6: Mock Financial Operations

**Files:**
- Create: `services/financial_ops.py`
- Test: `tests/test_financial_ops.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_financial_ops.py
from services.financial_ops import (
    process_upi_payment,
    get_balance_message,
    activate_insurance,
    open_savings,
    get_pf_nps_balance_message,
)


def test_upi_payment_success():
    result = process_upi_payment(
        sender_phone="9876543210",
        recipient_phone="8765432109",
        amount=500.0,
    )
    assert result["success"] is True
    assert "500" in result["message"]


def test_upi_payment_insufficient_funds():
    result = process_upi_payment(
        sender_phone="9876543210",
        recipient_phone="8765432109",
        amount=999999.0,
    )
    assert result["success"] is False


def test_upi_payment_unknown_recipient():
    result = process_upi_payment(
        sender_phone="9876543210",
        recipient_phone="0000000000",
        amount=100.0,
    )
    assert result["success"] is False
    assert result["error"] == "recipient_not_found"


def test_get_balance_message():
    msg = get_balance_message("9876543210", "en")
    assert "15000" in msg or "15,000" in msg


def test_activate_insurance():
    result = activate_insurance("9876543210", "health")
    assert result["success"] is True


def test_open_savings_fd():
    result = open_savings("9876543210", "fd", 2000.0, 12)
    assert result["success"] is True


def test_get_pf_nps():
    msg = get_pf_nps_balance_message("9876543210", "en")
    assert "120000" in msg or "1,20,000" in msg or "PF" in msg
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_financial_ops.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write services/financial_ops.py**

```python
"""
Mock implementations of all financial operations.
All mutations write back to the JSON data files.
"""
from datetime import date
from mock_db import (
    get_user, get_account, get_transactions,
    update_account_balance, add_transaction,
    update_user, update_account,
)


def _fmt_amount(amount: float) -> str:
    """Format amount as Indian rupee string."""
    return f"₹{amount:,.0f}"


def process_upi_payment(sender_phone: str, recipient_phone: str, amount: float) -> dict:
    sender = get_user(sender_phone)
    recipient = get_user(recipient_phone)

    if not sender:
        return {"success": False, "error": "sender_not_found"}
    if not recipient:
        return {"success": False, "error": "recipient_not_found"}

    sender_account = get_account(sender["account_id"])
    if not sender_account:
        return {"success": False, "error": "account_error"}

    if sender_account["balance"] < amount:
        return {"success": False, "error": "insufficient_funds"}

    # Debit sender, credit recipient
    update_account_balance(sender["account_id"], -amount)
    update_account_balance(recipient["account_id"], amount)

    today = date.today().isoformat()
    add_transaction(sender_phone, {"date": today, "type": "send", "amount": amount, "status": "success"})
    add_transaction(recipient_phone, {"date": today, "type": "receive", "amount": amount, "status": "success"})

    return {
        "success": True,
        "message": f"Payment of {_fmt_amount(amount)} to {recipient['name']} successful.",
    }


def get_balance_message(phone: str, lang_key: str) -> str:
    user = get_user(phone)
    if not user:
        return "Account not found."
    account = get_account(user["account_id"])
    if not account:
        return "Account not found."
    balance = account["balance"]
    return f"Your current balance is {_fmt_amount(balance)}."


def activate_insurance(phone: str, insurance_type: str) -> dict:
    """
    insurance_type: 'health', 'accident', 'crop'
    Premium deducted: health=₹50/month, accident=₹30/month, crop=₹100/month
    """
    user = get_user(phone)
    if not user:
        return {"success": False, "error": "user_not_found"}

    premium_map = {"health": 50, "accident": 30, "crop": 100}
    premium = premium_map.get(insurance_type, 50)

    account = get_account(user["account_id"])
    if account["balance"] < premium:
        return {"success": False, "error": "insufficient_funds"}

    update_account_balance(user["account_id"], -premium)

    active = user.get("insurance_active", [])
    if insurance_type not in active:
        active.append(insurance_type)
    update_user(phone, {"insurance_active": active})

    return {
        "success": True,
        "type": insurance_type,
        "premium": premium,
        "message": f"{insurance_type.title()} insurance activated. Monthly premium: {_fmt_amount(premium)}.",
    }


def open_savings(phone: str, savings_type: str, amount: float, duration_months: int) -> dict:
    """
    savings_type: 'fd' or 'rd'
    """
    user = get_user(phone)
    if not user:
        return {"success": False, "error": "user_not_found"}

    account = get_account(user["account_id"])
    if account["balance"] < amount:
        return {"success": False, "error": "insufficient_funds"}

    update_account_balance(user["account_id"], -amount)

    if savings_type == "fd":
        interest_rate = 7.5 if duration_months >= 12 else 6.5
        update_account(user["account_id"], {
            "fd_balance": account.get("fd_balance", 0) + amount,
            "fd_duration_months": duration_months,
            "fd_interest_rate": interest_rate,
        })
        return {
            "success": True,
            "message": f"Fixed deposit of {_fmt_amount(amount)} for {duration_months} months at {interest_rate}% p.a. opened.",
        }
    else:  # rd
        update_account(user["account_id"], {
            "rd_monthly": account.get("rd_monthly", 0) + amount,
        })
        return {
            "success": True,
            "message": f"Recurring deposit of {_fmt_amount(amount)} per month started.",
        }


def get_pf_nps_balance_message(phone: str, lang_key: str) -> str:
    user = get_user(phone)
    if not user:
        return "Account not found."
    account = get_account(user["account_id"])
    pf = account.get("pf_balance", 0)
    nps = account.get("nps_balance", 0)
    parts = []
    if pf > 0:
        parts.append(f"Your PF balance is {_fmt_amount(pf)}")
    if nps > 0:
        parts.append(f"Your NPS balance is {_fmt_amount(nps)}")
    if not parts:
        return "No PF or NPS balance found in your account."
    return ". ".join(parts) + "."
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_financial_ops.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/financial_ops.py tests/test_financial_ops.py
git commit -m "feat: mock financial operations (UPI, balance, insurance, savings, PF/NPS)"
```

---

## Task 7: Main Flask App — Entry + Language + Auth Flow

**Files:**
- Create: `app.py`

This task covers: call entry → language selection → phone number entry → mPIN verification → main menu.

- [ ] **Step 1: Write app.py (Part 1: scaffolding + call state + audio helpers)**

```python
# app.py
import os
import io
from pathlib import Path
from threading import Thread
from datetime import date

from flask import Flask, request, Response, send_from_directory

from config import LANG_CONFIG, STATIC_PROMPTS
from mock_db import get_user, get_account, get_transactions
from services.credit_score import calculate_credit_score, get_loan_terms
from services.financial_ops import (
    process_upi_payment,
    get_balance_message,
    activate_insurance,
    open_savings,
    get_pf_nps_balance_message,
)
from services.sarvam_tts import save_tts

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
PROMPT_DIR = BASE_DIR / "prompt_audio"
DYN_AUDIO_DIR = BASE_DIR / "dynamic_audio"
DYN_AUDIO_DIR.mkdir(exist_ok=True)

# Per-call state keyed by CallSid
CALL_STATE: dict[str, dict] = {}


def play(lang_key: str, prompt: str) -> str:
    """Return a TwiML <Play> tag for a static pre-generated prompt."""
    filename = f"{lang_key}_{prompt}.mp3"
    return f"<Play>/audio/{filename}</Play>"


def play_dynamic(text: str, lang_key: str, call_sid: str) -> str:
    """
    Generate TTS on-the-fly for dynamic content (amounts, scores, names).
    Saves the MP3 to dynamic_audio/ and returns a <Play> tag.
    Falls back to <Say> on TTS failure.
    """
    safe_sid = call_sid.replace(" ", "_")[:32]
    filename = f"dyn_{safe_sid}_{lang_key}.mp3"
    out_path = DYN_AUDIO_DIR / filename

    success = save_tts(text, lang_key, out_path)
    if success:
        return f"<Play>/dynamic-audio/{filename}</Play>"
    else:
        return f"<Say language='{lang_key}-IN'>{text}</Say>"


def twiml(body: str) -> Response:
    return Response(f"<Response>{body}</Response>", mimetype="text/xml")
```

- [ ] **Step 2: Add entry route + language menu**

Append to `app.py`:

```python
# -------------------------------------------------------
# ROUTE 1: Entry — Play language selection menu
# -------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def voice_entry():
    call_sid = request.form.get("CallSid", "unknown")
    CALL_STATE[call_sid] = {"attempts": 0}

    body = f"""
        <Gather input="dtmf" numDigits="1" timeout="8" action="/handle-language" method="POST">
            {play("en", "lang_menu")}
        </Gather>
        {play("en", "invalid")}
        <Redirect>/</Redirect>
    """
    return twiml(body)


# -------------------------------------------------------
# ROUTE 2: Handle language digit
# -------------------------------------------------------
@app.route("/handle-language", methods=["POST"])
def handle_language():
    call_sid = request.form.get("CallSid", "")
    digit = (request.form.get("Digits") or "").strip()
    config = LANG_CONFIG.get(digit)

    if not config:
        return twiml(f"{play('en', 'invalid')}<Redirect>/</Redirect>")

    lang_key = config["lang_key"]
    CALL_STATE[call_sid] = {"lang_key": lang_key, "attempts": 0}

    body = f"""
        <Gather input="dtmf" numDigits="10" timeout="15" action="/handle-phone" method="POST">
            {play(lang_key, "enter_phone")}
        </Gather>
        {play(lang_key, "invalid")}
        <Redirect>/handle-language</Redirect>
    """
    return twiml(body)


# -------------------------------------------------------
# ROUTE 3: Handle phone number entry
# -------------------------------------------------------
@app.route("/handle-phone", methods=["POST"])
def handle_phone():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    digits = (request.form.get("Digits") or "").strip()

    if not digits or len(digits) != 10:
        return twiml(f"""
            {play(lang_key, "invalid")}
            <Gather input="dtmf" numDigits="10" timeout="15" action="/handle-phone" method="POST">
                {play(lang_key, "enter_phone")}
            </Gather>
            {play(lang_key, "goodbye")}
            <Hangup/>
        """)

    user = get_user(digits)
    if not user:
        return twiml(f"{play(lang_key, 'no_account')}<Hangup/>")

    state["phone"] = digits
    state["mpin_attempts"] = 0
    CALL_STATE[call_sid] = state

    body = f"""
        <Gather input="dtmf" numDigits="4" timeout="10" action="/handle-mpin" method="POST">
            {play(lang_key, "enter_mpin")}
        </Gather>
        {play(lang_key, "invalid")}
        <Redirect>/handle-phone</Redirect>
    """
    return twiml(body)


# -------------------------------------------------------
# ROUTE 4: Handle mPIN verification
# -------------------------------------------------------
@app.route("/handle-mpin", methods=["POST"])
def handle_mpin():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    phone = state.get("phone", "")
    digits = (request.form.get("Digits") or "").strip()

    user = get_user(phone)
    if not user or digits != user["mpin"]:
        state["mpin_attempts"] = state.get("mpin_attempts", 0) + 1
        CALL_STATE[call_sid] = state

        if state["mpin_attempts"] >= 3:
            return twiml(f"{play(lang_key, 'mpin_locked')}<Hangup/>")

        body = f"""
            {play(lang_key, "wrong_mpin")}
            <Gather input="dtmf" numDigits="4" timeout="10" action="/handle-mpin" method="POST">
                {play(lang_key, "enter_mpin")}
            </Gather>
            {play(lang_key, "goodbye")}
            <Hangup/>
        """
        return twiml(body)

    # Auth success
    state["authenticated"] = True
    state["name"] = user["name"]
    CALL_STATE[call_sid] = state

    body = f"""
        {play(lang_key, "auth_success")}
        <Redirect>/main-menu</Redirect>
    """
    return twiml(body)
```

- [ ] **Step 3: Add main menu route**

Append to `app.py`:

```python
# -------------------------------------------------------
# ROUTE 5: Main service menu
# -------------------------------------------------------
@app.route("/main-menu", methods=["GET", "POST"])
def main_menu():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")

    body = f"""
        <Gather input="dtmf" numDigits="1" timeout="10" action="/handle-menu" method="POST">
            {play(lang_key, "main_menu")}
        </Gather>
        {play(lang_key, "invalid")}
        <Redirect>/main-menu</Redirect>
    """
    return twiml(body)


# -------------------------------------------------------
# ROUTE 6: Route menu selection to service
# -------------------------------------------------------
@app.route("/handle-menu", methods=["POST"])
def handle_menu():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    digit = (request.form.get("Digits") or "").strip()

    routes = {
        "1": "/upi/ask-recipient",
        "2": "/balance/check",
        "3": "/loan/check-eligibility",
        "4": "/insurance/menu",
        "5": "/credit/check",
        "6": "/savings/menu",
        "7": "/pf/check",
    }
    dest = routes.get(digit)
    if not dest:
        return twiml(f"{play(lang_key, 'invalid')}<Redirect>/main-menu</Redirect>")
    return twiml(f"<Redirect>{dest}</Redirect>")
```

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: IVR entry, language selection, phone+mPIN auth, main menu routing"
```

---

## Task 8: UPI Payment Flow

**Files:**
- Modify: `app.py` (append UPI routes)

- [ ] **Step 1: Append UPI routes to app.py**

```python
# -------------------------------------------------------
# UPI PAYMENT FLOW
# -------------------------------------------------------
@app.route("/upi/ask-recipient", methods=["GET", "POST"])
def upi_ask_recipient():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")

    body = f"""
        <Gather input="dtmf" numDigits="10" timeout="15" action="/upi/handle-recipient" method="POST">
            {play(lang_key, "upi_ask_recipient")}
        </Gather>
        {play(lang_key, "invalid")}
        <Redirect>/main-menu</Redirect>
    """
    return twiml(body)


@app.route("/upi/handle-recipient", methods=["POST"])
def upi_handle_recipient():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    digits = (request.form.get("Digits") or "").strip()

    if not digits or len(digits) != 10:
        return twiml(f"{play(lang_key, 'invalid')}<Redirect>/upi/ask-recipient</Redirect>")

    recipient = get_user(digits)
    if not recipient:
        return twiml(f"{play(lang_key, 'upi_not_found')}<Redirect>/main-menu</Redirect>")

    state["upi_recipient_phone"] = digits
    state["upi_recipient_name"] = recipient["name"]
    CALL_STATE[call_sid] = state

    body = f"""
        <Gather input="dtmf" numDigits="6" timeout="15" finishOnKey="#" action="/upi/handle-amount" method="POST">
            {play(lang_key, "upi_ask_amount")}
        </Gather>
        {play(lang_key, "invalid")}
        <Redirect>/main-menu</Redirect>
    """
    return twiml(body)


@app.route("/upi/handle-amount", methods=["POST"])
def upi_handle_amount():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    digits = (request.form.get("Digits") or "").strip().rstrip("#")

    if not digits.isdigit() or int(digits) <= 0:
        return twiml(f"{play(lang_key, 'invalid')}<Redirect>/upi/ask-recipient</Redirect>")

    state["upi_amount"] = int(digits)
    CALL_STATE[call_sid] = state

    body = f"""
        <Gather input="dtmf" numDigits="1" timeout="8" action="/upi/execute" method="POST">
            {play(lang_key, "upi_confirm")}
        </Gather>
        {play(lang_key, "invalid")}
        <Redirect>/main-menu</Redirect>
    """
    return twiml(body)


@app.route("/upi/execute", methods=["POST"])
def upi_execute():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    digit = (request.form.get("Digits") or "").strip()

    if digit != "1":
        return twiml(f"{play(lang_key, 'goodbye')}<Hangup/>")

    result = process_upi_payment(
        sender_phone=state.get("phone", ""),
        recipient_phone=state.get("upi_recipient_phone", ""),
        amount=float(state.get("upi_amount", 0)),
    )

    if result["success"]:
        dyn = play_dynamic(result["message"], lang_key, call_sid)
        return twiml(f"{play(lang_key, 'upi_success')}{dyn}{play(lang_key, 'goodbye')}<Hangup/>")
    else:
        return twiml(f"{play(lang_key, 'upi_failed')}<Redirect>/main-menu</Redirect>")
```

- [ ] **Step 2: Commit**

```bash
git add app.py
git commit -m "feat: UPI payment IVR flow (recipient, amount, confirm, execute)"
```

---

## Task 9: Balance + Credit Score + PF/NPS Flows

**Files:**
- Modify: `app.py` (append balance, credit, PF routes)

- [ ] **Step 1: Append balance check route**

```python
# -------------------------------------------------------
# BALANCE CHECK
# -------------------------------------------------------
@app.route("/balance/check", methods=["GET", "POST"])
def balance_check():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    phone = state.get("phone", "")

    msg = get_balance_message(phone, lang_key)
    dyn = play_dynamic(msg, lang_key, call_sid)
    return twiml(f"{dyn}<Redirect>/main-menu</Redirect>")
```

- [ ] **Step 2: Append credit score route**

```python
# -------------------------------------------------------
# CREDIT SCORE
# -------------------------------------------------------
@app.route("/credit/check", methods=["GET", "POST"])
def credit_check():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    phone = state.get("phone", "")

    user = get_user(phone)
    transactions = get_transactions(phone)
    score, factors = calculate_credit_score(transactions, user or {})
    terms = get_loan_terms(score)

    factor_text = " and ".join(factors)
    if terms["eligible"]:
        msg = (
            f"Your VaaniPay credit score is {score}. "
            f"Your top positive factors are {factor_text}. "
            f"You are eligible for a loan up to {terms['max_amount']} rupees "
            f"at {terms['interest_rate']} percent per annum."
        )
    else:
        msg = (
            f"Your VaaniPay credit score is {score}. "
            f"Your top factors are {factor_text}. "
            f"Keep using VaaniPay to improve your score and become eligible for loans."
        )

    dyn = play_dynamic(msg, lang_key, call_sid)
    return twiml(f"{dyn}<Redirect>/main-menu</Redirect>")
```

- [ ] **Step 3: Append PF/NPS route**

```python
# -------------------------------------------------------
# PF / NPS BALANCE
# -------------------------------------------------------
@app.route("/pf/check", methods=["GET", "POST"])
def pf_check():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    phone = state.get("phone", "")

    msg = get_pf_nps_balance_message(phone, lang_key)
    dyn = play_dynamic(msg, lang_key, call_sid)
    return twiml(f"{dyn}<Redirect>/main-menu</Redirect>")
```

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: balance check, credit score, and PF/NPS IVR flows"
```

---

## Task 10: Loan Flow

**Files:**
- Modify: `app.py` (append loan routes)

- [ ] **Step 1: Append loan routes**

```python
# -------------------------------------------------------
# MICRO LOAN FLOW
# -------------------------------------------------------
@app.route("/loan/check-eligibility", methods=["GET", "POST"])
def loan_check_eligibility():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    phone = state.get("phone", "")

    user = get_user(phone)
    transactions = get_transactions(phone)
    score, _ = calculate_credit_score(transactions, user or {})
    terms = get_loan_terms(score)

    state["credit_score"] = score
    state["loan_terms"] = terms
    CALL_STATE[call_sid] = state

    if not terms["eligible"]:
        return twiml(f"{play(lang_key, 'loan_not_eligible')}<Redirect>/main-menu</Redirect>")

    eligibility_msg = (
        f"Your credit score is {score}. You are eligible for a loan up to "
        f"{terms['max_amount']} rupees at {terms['interest_rate']} percent per annum."
    )
    dyn = play_dynamic(eligibility_msg, lang_key, call_sid)

    body = f"""
        {dyn}
        <Gather input="dtmf" numDigits="5" timeout="15" finishOnKey="#" action="/loan/handle-amount" method="POST">
            {play(lang_key, "loan_ask_amount")}
        </Gather>
        {play(lang_key, "invalid")}
        <Redirect>/main-menu</Redirect>
    """
    return twiml(body)


@app.route("/loan/handle-amount", methods=["POST"])
def loan_handle_amount():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    digits = (request.form.get("Digits") or "").strip().rstrip("#")

    if not digits.isdigit():
        return twiml(f"{play(lang_key, 'invalid')}<Redirect>/main-menu</Redirect>")

    amount = int(digits)
    terms = state.get("loan_terms", {})
    max_amount = terms.get("max_amount", 0)

    if amount < 500 or amount > max_amount:
        over_msg = f"Amount must be between 500 and {max_amount} rupees."
        dyn = play_dynamic(over_msg, lang_key, call_sid)
        body = f"""
            {dyn}
            <Gather input="dtmf" numDigits="5" timeout="15" finishOnKey="#" action="/loan/handle-amount" method="POST">
                {play(lang_key, "loan_ask_amount")}
            </Gather>
            {play(lang_key, "invalid")}
            <Redirect>/main-menu</Redirect>
        """
        return twiml(body)

    state["loan_amount"] = amount
    CALL_STATE[call_sid] = state

    rate = terms.get("interest_rate", 15)
    confirm_msg = f"Loan of {amount} rupees at {rate} percent per annum for 12 months. Monthly EMI approximately {int(amount * (rate/1200 * (1+rate/1200)**12) / ((1+rate/1200)**12 - 1))} rupees."
    dyn = play_dynamic(confirm_msg, lang_key, call_sid)

    body = f"""
        {dyn}
        <Gather input="dtmf" numDigits="1" timeout="8" action="/loan/execute" method="POST">
            {play(lang_key, "loan_confirm")}
        </Gather>
        {play(lang_key, "invalid")}
        <Redirect>/main-menu</Redirect>
    """
    return twiml(body)


@app.route("/loan/execute", methods=["POST"])
def loan_execute():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    digit = (request.form.get("Digits") or "").strip()
    phone = state.get("phone", "")

    if digit != "1":
        return twiml(f"{play(lang_key, 'goodbye')}<Hangup/>")

    amount = state.get("loan_amount", 0)
    from mock_db import update_account_balance, update_user, add_transaction
    from datetime import date

    user = get_user(phone)
    if not user:
        return twiml(f"{play(lang_key, 'error')}<Hangup/>")

    update_account_balance(user["account_id"], amount)
    update_user(phone, {"loan_active": True, "loan_outstanding": amount})
    add_transaction(phone, {
        "date": date.today().isoformat(),
        "type": "loan_disbursed",
        "amount": amount,
        "status": "success",
    })

    dyn = play_dynamic(f"Loan of {amount} rupees has been credited to your account.", lang_key, call_sid)
    return twiml(f"{play(lang_key, 'loan_approved')}{dyn}{play(lang_key, 'goodbye')}<Hangup/>")
```

- [ ] **Step 2: Commit**

```bash
git add app.py
git commit -m "feat: micro-loan IVR flow with credit-score-based eligibility"
```

---

## Task 11: Insurance + Savings Flows

**Files:**
- Modify: `app.py` (append insurance + savings routes)

- [ ] **Step 1: Append insurance routes**

```python
# -------------------------------------------------------
# MICRO INSURANCE FLOW
# -------------------------------------------------------
INSURANCE_TYPES = {"1": "health", "2": "accident", "3": "crop"}
INSURANCE_PREMIUMS = {"health": 50, "accident": 30, "crop": 100}

@app.route("/insurance/menu", methods=["GET", "POST"])
def insurance_menu():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")

    body = f"""
        <Gather input="dtmf" numDigits="1" timeout="8" action="/insurance/handle-type" method="POST">
            {play(lang_key, "insurance_menu")}
        </Gather>
        {play(lang_key, "invalid")}
        <Redirect>/main-menu</Redirect>
    """
    return twiml(body)


@app.route("/insurance/handle-type", methods=["POST"])
def insurance_handle_type():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    digit = (request.form.get("Digits") or "").strip()

    insurance_type = INSURANCE_TYPES.get(digit)
    if not insurance_type:
        return twiml(f"{play(lang_key, 'invalid')}<Redirect>/insurance/menu</Redirect>")

    premium = INSURANCE_PREMIUMS[insurance_type]
    state["insurance_type"] = insurance_type
    CALL_STATE[call_sid] = state

    confirm_msg = f"{insurance_type.title()} insurance. Monthly premium {premium} rupees."
    dyn = play_dynamic(confirm_msg, lang_key, call_sid)

    body = f"""
        {dyn}
        <Gather input="dtmf" numDigits="1" timeout="8" action="/insurance/execute" method="POST">
            {play(lang_key, "insurance_confirm")}
        </Gather>
        {play(lang_key, "invalid")}
        <Redirect>/main-menu</Redirect>
    """
    return twiml(body)


@app.route("/insurance/execute", methods=["POST"])
def insurance_execute():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    digit = (request.form.get("Digits") or "").strip()
    phone = state.get("phone", "")

    if digit != "1":
        return twiml(f"{play(lang_key, 'goodbye')}<Hangup/>")

    result = activate_insurance(phone, state.get("insurance_type", "health"))
    if result["success"]:
        return twiml(f"{play(lang_key, 'insurance_success')}<Redirect>/main-menu</Redirect>")
    else:
        return twiml(f"{play(lang_key, 'error')}<Redirect>/main-menu</Redirect>")
```

- [ ] **Step 2: Append savings routes**

```python
# -------------------------------------------------------
# SAVINGS FLOW (FD / RD)
# -------------------------------------------------------
@app.route("/savings/menu", methods=["GET", "POST"])
def savings_menu():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")

    body = f"""
        <Gather input="dtmf" numDigits="1" timeout="8" action="/savings/handle-type" method="POST">
            {play(lang_key, "savings_menu")}
        </Gather>
        {play(lang_key, "invalid")}
        <Redirect>/main-menu</Redirect>
    """
    return twiml(body)


@app.route("/savings/handle-type", methods=["POST"])
def savings_handle_type():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    digit = (request.form.get("Digits") or "").strip()

    savings_type = {"1": "fd", "2": "rd"}.get(digit)
    if not savings_type:
        return twiml(f"{play(lang_key, 'invalid')}<Redirect>/savings/menu</Redirect>")

    state["savings_type"] = savings_type
    CALL_STATE[call_sid] = state

    body = f"""
        <Gather input="dtmf" numDigits="6" timeout="15" finishOnKey="#" action="/savings/handle-amount" method="POST">
            {play(lang_key, "savings_ask_amount")}
        </Gather>
        {play(lang_key, "invalid")}
        <Redirect>/main-menu</Redirect>
    """
    return twiml(body)


@app.route("/savings/handle-amount", methods=["POST"])
def savings_handle_amount():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    digits = (request.form.get("Digits") or "").strip().rstrip("#")

    if not digits.isdigit() or int(digits) < 100:
        return twiml(f"{play(lang_key, 'invalid')}<Redirect>/savings/menu</Redirect>")

    state["savings_amount"] = int(digits)
    CALL_STATE[call_sid] = state

    body = f"""
        <Gather input="dtmf" numDigits="2" timeout="10" finishOnKey="#" action="/savings/handle-duration" method="POST">
            {play(lang_key, "savings_ask_duration")}
        </Gather>
        {play(lang_key, "invalid")}
        <Redirect>/main-menu</Redirect>
    """
    return twiml(body)


@app.route("/savings/handle-duration", methods=["POST"])
def savings_handle_duration():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    digits = (request.form.get("Digits") or "").strip().rstrip("#")

    if not digits.isdigit() or int(digits) < 1:
        return twiml(f"{play(lang_key, 'invalid')}<Redirect>/savings/menu</Redirect>")

    state["savings_duration"] = int(digits)
    CALL_STATE[call_sid] = state

    amount = state.get("savings_amount", 0)
    duration = int(digits)
    savings_type = state.get("savings_type", "fd")
    confirm_msg = f"{savings_type.upper()} of {amount} rupees for {duration} months."
    dyn = play_dynamic(confirm_msg, lang_key, call_sid)

    body = f"""
        {dyn}
        <Gather input="dtmf" numDigits="1" timeout="8" action="/savings/execute" method="POST">
            {play(lang_key, "savings_confirm")}
        </Gather>
        {play(lang_key, "invalid")}
        <Redirect>/main-menu</Redirect>
    """
    return twiml(body)


@app.route("/savings/execute", methods=["POST"])
def savings_execute():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    digit = (request.form.get("Digits") or "").strip()
    phone = state.get("phone", "")

    if digit != "1":
        return twiml(f"{play(lang_key, 'goodbye')}<Hangup/>")

    result = open_savings(
        phone=phone,
        savings_type=state.get("savings_type", "fd"),
        amount=float(state.get("savings_amount", 0)),
        duration_months=state.get("savings_duration", 12),
    )

    if result["success"]:
        dyn = play_dynamic(result["message"], lang_key, call_sid)
        return twiml(f"{play(lang_key, 'savings_success')}{dyn}<Redirect>/main-menu</Redirect>")
    else:
        return twiml(f"{play(lang_key, 'error')}<Redirect>/main-menu</Redirect>")
```

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: micro-insurance and savings (FD/RD) IVR flows"
```

---

## Task 12: Static File Routes + App Startup

**Files:**
- Modify: `app.py` (append static file routes + run block)

- [ ] **Step 1: Append static routes + run block**

```python
# -------------------------------------------------------
# STATIC FILE SERVING
# -------------------------------------------------------
@app.route("/audio/<path:filename>")
def serve_prompt_audio(filename):
    return send_from_directory(PROMPT_DIR, filename, mimetype="audio/mpeg")


@app.route("/dynamic-audio/<path:filename>")
def serve_dynamic_audio(filename):
    return send_from_directory(DYN_AUDIO_DIR, filename, mimetype="audio/mpeg")


# -------------------------------------------------------
# HEALTH CHECK
# -------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "service": "VaaniPay IVR"}


# -------------------------------------------------------
# CLEANUP ON CALL END
# -------------------------------------------------------
@app.route("/call-complete", methods=["POST"])
def call_complete():
    call_sid = request.form.get("CallSid", "")
    if call_sid in CALL_STATE:
        del CALL_STATE[call_sid]
    return {"status": "cleaned"}


# -------------------------------------------------------
# STARTUP
# -------------------------------------------------------
if __name__ == "__main__":
    # Expose via ngrok: ngrok http 5000
    # Then set Twilio Voice webhook to: https://<ngrok-id>.ngrok.io/
    app.run(host="0.0.0.0", port=5000, debug=True)
```

- [ ] **Step 2: Run the server locally and verify the /health endpoint**

```bash
python app.py
```

In a second terminal:
```bash
curl http://localhost:5000/health
```

Expected: `{"service": "VaaniPay IVR", "status": "ok"}`

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: static file serving, health check, call cleanup, app startup"
```

---

## Task 13: ngrok + Twilio Wiring

**Files:**
- Create: `SETUP.md` (not tracked in plan — this is documentation)

This task has no code. It's the deployment wiring.

- [ ] **Step 1: Start the Flask server**

```bash
python app.py
```

Expected: `Running on http://0.0.0.0:5000`

- [ ] **Step 2: Start ngrok in a separate terminal**

```bash
ngrok http 5000
```

Expected: `Forwarding  https://abcd1234.ngrok.io -> http://localhost:5000`

Copy the `https://` URL.

- [ ] **Step 3: Configure Twilio webhook**

1. Log in to Twilio console
2. Go to Phone Numbers → Manage → Active Numbers
3. Click your VaaniPay number
4. Under Voice & Fax → A call comes in:
   - Set to **Webhook**
   - URL: `https://abcd1234.ngrok.io/` (your ngrok URL)
   - HTTP: POST
5. Under Call Status Changes:
   - URL: `https://abcd1234.ngrok.io/call-complete`
6. Save

- [ ] **Step 4: Test by calling your Twilio number**

Dial the Twilio number from any phone.

Expected: You hear the English language menu prompt (`lang_menu`). Pressing 1 plays the Hindi menu, entering your 10-digit phone gives mPIN prompt, etc.

- [ ] **Step 5: Commit final state**

```bash
git add .
git commit -m "feat: complete VaaniPay IVR system - all flows integrated"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Implemented in |
|---|---|
| IVR via Twilio | Task 7–12, all `app.py` routes |
| 9 Indian languages (DTMF selection) | Task 1 `LANG_CONFIG`, Task 7 `voice_entry` |
| mPIN authentication | Task 7 `handle_mpin` |
| UPI payment by voice | Task 8 UPI flow |
| Balance inquiry | Task 9 `balance_check` |
| Micro-loan with credit score | Task 10 loan flow |
| Micro-insurance (health/accident/crop) | Task 11 insurance flow |
| Behavioral credit scoring 300–900 | Task 5 `credit_score.py` |
| FD/RD savings | Task 11 savings flow |
| PF/NPS balance | Task 9 `pf_check` |
| Sarvam AI TTS for responses | Task 3 `sarvam_tts.py`, used throughout |
| Dynamic TTS for amounts/scores | Task 7 `play_dynamic()` |
| Mock backend data | Task 2 `mock_db.py` + JSON files |

**No placeholders found** — all steps have complete code.

**Type consistency check:**
- `get_user()` → returns `dict | None` — all callers check for `None` ✓
- `calculate_credit_score()` → returns `tuple[int, list[str]]` — Task 9, 10 both unpack correctly ✓
- `get_loan_terms()` → returns `dict` with keys `eligible`, `max_amount`, `interest_rate` — Task 10 uses all three ✓
- `play_dynamic()` → returns `str` (TwiML fragment) — used correctly everywhere ✓
