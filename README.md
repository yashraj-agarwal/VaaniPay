# VaaniPay — Voice-First IVR Financial Inclusion Platform

A voice-only financial assistant for feature phones. Users dial a Twilio number and can send UPI payments, check balance, apply for micro-loans, buy insurance, check credit score, open savings, and check PF/NPS — entirely by voice, in 9 Indian languages. No smartphone or internet required on the caller's end.

**Built for:** ACM Hackathon 1.0 — PS3: FinTech for Financial Inclusion

---

## Prerequisites

You need accounts/API keys for:
- **Twilio** — free trial at twilio.com (gives you a phone number + $15 credit)
- **Sarvam AI** — API key from api.sarvam.ai (for Indian language TTS)
- **ngrok** — free tunnel to expose your local server to Twilio

---

## Setup (Windows)

### 1. Install Python

Download Python 3.11+ from **python.org/downloads**. During install, tick **"Add Python to PATH"**.

Verify:
```
python --version
```

### 2. Clone the repo

```
git clone https://github.com/kisnaXD/acm-manipal-vaanipay
cd acm-manipal-vaanipay
```

### 3. Create a virtual environment

```
python -m venv venv
venv\Scripts\activate
```

You'll see `(venv)` in your terminal. Run all subsequent commands inside this.

### 4. Install dependencies

```
pip install -r requirements.txt
```

### 5. Set up environment variables

Copy the example file:
```
copy .env.example .env
```

Open `.env` in Notepad (or any editor) and fill in your keys:

```
SARVAM_API_KEY=your_key_from_api.sarvam.ai
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX
SERVER_BASE_URL=https://your-ngrok-url.ngrok.io
```

Where to get each:
- `SARVAM_API_KEY` → Log in at api.sarvam.ai → API Keys
- `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` → Twilio Console dashboard (top of page)
- `TWILIO_PHONE_NUMBER` → Twilio Console → Phone Numbers → Manage → Active Numbers
- `SERVER_BASE_URL` → fill this in after step 8 (ngrok URL)

### 6. Generate audio prompt files

This downloads all IVR audio prompts (~260 WAV files) from Sarvam AI TTS. Run once:

```
python download_audios.py
```

This takes 3–5 minutes. Progress is shown line by line. If any fail, just re-run — it skips already-downloaded files automatically.

Once done, you'll have a `prompt_audio/` folder with files like `hi_main_menu.wav`, `en_enter_phone.wav`, etc.

### 7. Start the Flask server

```
python app.py
```

You should see:
```
* Running on http://0.0.0.0:5000
```

Leave this terminal open.

### 8. Install and run ngrok

Download ngrok from **ngrok.com/download** → Windows → extract the `.exe`.

In a **new terminal** (keep Flask running in the first one):
```
ngrok http 5000
```

You'll see something like:
```
Forwarding   https://abcd1234.ngrok-free.app -> http://localhost:5000
```

Copy the `https://` URL. Put it in your `.env` as `SERVER_BASE_URL`.

### 9. Wire up Twilio

1. Log in to **console.twilio.com**
2. Go to **Phone Numbers → Manage → Active Numbers**
3. Click your VaaniPay number
4. Under **Voice Configuration → A call comes in**:
   - Select: **Webhook**
   - URL: `https://abcd1234.ngrok-free.app/` (your ngrok URL + trailing slash)
   - HTTP Method: **POST**
5. Under **Call Status Changes**:
   - URL: `https://abcd1234.ngrok-free.app/call-complete`
6. Click **Save**

> **Free trial note:** Twilio trial accounts can only call **verified numbers**. Go to Twilio Console → Verified Caller IDs → add your phone number before testing.

### 10. Call and test

Dial your Twilio number from your phone. You should hear the language menu.

Test flow:
- Press **1** for Hindi (or any 1–9 for other languages)
- Enter phone: `9876543210` (demo user)
- Enter mPIN: `1234`
- Press **2** for balance → hear balance in Hindi
- Press **3** for loan → hear credit score + eligibility

---

## Demo User Accounts

The mock database (`data/`) has 3 pre-loaded users:

| Phone | mPIN | Name | Language | Balance |
|-------|------|------|----------|---------|
| `9876543210` | `1234` | Ramesh Kumar | Hindi | ₹15,000 |
| `8765432109` | `5678` | Priya Devi | Tamil | ₹8,200 |
| `7654321098` | `9012` | Suresh Babu | Telugu | ₹3,500 |

---

## IVR Call Flow

```
Dial VaaniPay number
  └─ Language menu (press 1–9)
       └─ Enter 10-digit phone number
            └─ Enter 4-digit mPIN (3 attempts max)
                 └─ Main menu
                      ├─ 1: UPI Payment  → recipient → amount → confirm
                      ├─ 2: Balance      → read aloud in your language
                      ├─ 3: Micro Loan   → credit check → amount → confirm
                      ├─ 4: Insurance    → health / accident / crop
                      ├─ 5: Credit Score → 300–900 score + top factors
                      ├─ 6: Savings      → FD or RD → amount → duration
                      └─ 7: PF / NPS     → balance read aloud
```

---

## File Structure

```
vaanipay/
├── app.py                  ← Flask server (all Twilio webhook routes)
├── config.py               ← Language config (9 langs, DTMF mapping)
├── mock_db.py              ← Read/write helpers for JSON data files
├── download_audios.py      ← Script to generate all audio prompts via Sarvam TTS
├── services/
│   ├── sarvam_tts.py      ← Sarvam AI TTS API client
│   ├── credit_score.py    ← Behavioral credit scoring (300–900)
│   └── financial_ops.py   ← Mock UPI, loan, insurance, savings, PF/NPS
├── data/
│   ├── users.json         ← User profiles (phone, mPIN, account)
│   ├── accounts.json      ← Balances, FD, PF, NPS
│   └── transactions.json  ← Transaction history (used for credit scoring)
├── prompt_audio/          ← Generated WAV files (gitignored, run download_audios.py)
├── dynamic_audio/         ← Runtime TTS for amounts/scores (auto-created)
├── requirements.txt
└── .env.example
```

---

## Supported Languages

| Key | Language | DTMF |
|-----|----------|------|
| hi | Hindi | 1 |
| en | English | 2 |
| ta | Tamil | 3 |
| te | Telugu | 4 |
| kn | Kannada | 5 |
| ml | Malayalam | 6 |
| mr | Marathi | 7 |
| bn | Bengali | 8 |
| gu | Gujarati | 9 |

---

## Troubleshooting

**"No audio plays when I call"**
→ Check that `prompt_audio/` exists and has `.wav` files. Run `python download_audios.py` if empty.

**"Twilio says webhook failed"**
→ Make sure Flask is running (`python app.py`) and ngrok is running in a separate terminal. Check the ngrok URL matches what's in Twilio.

**"download_audios.py fails with 400 error"**
→ Your `SARVAM_API_KEY` in `.env` may be wrong. Verify at api.sarvam.ai.

**"mPIN not accepted"**
→ Use the demo credentials above. Phone must be exactly 10 digits.

**"ngrok URL keeps changing"**
→ Free ngrok gives a new URL every restart. Re-paste it into Twilio and `.env` each time. A paid ngrok plan gives a fixed domain.
