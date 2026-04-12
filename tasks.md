# VaaniPay — Implementation Tasks

Full plan: `docs/superpowers/plans/2026-04-12-vaanipay-ivr.md`

---

## Phase 1: Setup

- [ ] Create `requirements.txt` with flask, twilio, requests, python-dotenv, pytest
- [ ] Create `.env.example` with SARVAM_API_KEY, TWILIO_*, SERVER_BASE_URL
- [ ] Write `config.py` — LANG_CONFIG (9 languages), STATIC_PROMPTS (all text per lang)
- [ ] `pip install -r requirements.txt`

## Phase 2: Data Layer

- [ ] Create `data/users.json` — 3 mock users with phone, mPIN, account_id
- [ ] Create `data/accounts.json` — balances, FD, PF, NPS per account
- [ ] Create `data/transactions.json` — 10–12 transaction records per user
- [ ] Write `mock_db.py` — helpers: `get_user`, `get_account`, `get_transactions`, `update_*`, `add_transaction`

## Phase 3: Services

- [ ] Write `services/sarvam_tts.py` — `generate_tts(text, lang_key) → bytes`, `save_tts(...)` → bool
- [ ] Write `services/credit_score.py` — `calculate_credit_score(txns, user) → (int, list[str])`, `get_loan_terms(score) → dict`
- [ ] Write `services/financial_ops.py` — `process_upi_payment`, `get_balance_message`, `activate_insurance`, `open_savings`, `get_pf_nps_balance_message`
- [ ] Write tests: `tests/test_credit_score.py` (3 tests) and `tests/test_financial_ops.py` (7 tests)
- [ ] Run `pytest tests/ -v` — all pass

## Phase 4: Audio Prompts

- [x] Write `download_audios.py` — iterates all prompts, calls Sarvam TTS, saves `prompt_audio/{lang}_{key}.wav`
- [ ] Run `python download_audios.py` — generates ~261 WAV files (9 lang_menu + 9×28 service prompts)

## Phase 5: IVR App

- [ ] Write `app.py` — Flask app skeleton: `CALL_STATE`, `play()`, `play_dynamic()`, `twiml()` helpers
- [ ] Add **entry + language** routes: `/`, `/handle-language`
- [ ] Add **auth** routes: `/handle-phone`, `/handle-mpin`
- [ ] Add **main menu** routes: `/main-menu`, `/handle-menu`
- [ ] Add **UPI payment** routes: `/upi/ask-recipient`, `/upi/handle-recipient`, `/upi/handle-amount`, `/upi/execute`
- [ ] Add **balance** route: `/balance/check`
- [ ] Add **credit score** route: `/credit/check`
- [ ] Add **loan** routes: `/loan/check-eligibility`, `/loan/handle-amount`, `/loan/execute`
- [ ] Add **insurance** routes: `/insurance/menu`, `/insurance/handle-type`, `/insurance/execute`
- [ ] Add **savings** routes: `/savings/menu`, `/savings/handle-type`, `/savings/handle-amount`, `/savings/handle-duration`, `/savings/execute`
- [ ] Add **PF/NPS** route: `/pf/check`
- [ ] Add static file routes: `/audio/<filename>`, `/dynamic-audio/<filename>`
- [ ] Add `/health` and `/call-complete` endpoints
- [ ] `python app.py` + `curl localhost:5000/health` → `{"status": "ok"}`

## Phase 6: Deployment & Testing

- [ ] Run `ngrok http 5000` — get public HTTPS URL
- [ ] Set Twilio webhook to `https://<ngrok-url>/` (Voice webhook, POST)
- [ ] Set Twilio status callback to `https://<ngrok-url>/call-complete`
- [ ] Call the Twilio number → hear language menu in English
- [ ] Test full flow: language → phone → mPIN → UPI payment
- [ ] Test: balance check, credit score, loan, insurance, savings, PF/NPS

---

## Call Flow Summary

```
Dial VaaniPay number
  └─ Language menu (press 1–9)
       └─ Enter 10-digit phone number
            └─ Enter 4-digit mPIN (3 attempts max)
                 └─ Main menu
                      ├─ 1: UPI Payment → recipient number → amount → confirm → execute
                      ├─ 2: Balance → read balance → back to menu
                      ├─ 3: Micro Loan → credit check → eligible? → amount → confirm → disburse
                      ├─ 4: Insurance → type (health/accident/crop) → confirm → activate
                      ├─ 5: Credit Score → calculate → read score + factors → back to menu
                      ├─ 6: Savings → type (FD/RD) → amount → duration → confirm → open
                      └─ 7: PF/NPS → read balance → back to menu
```

---

## File Structure

```
vaanipay/
├── app.py                    ← Main Flask IVR server (all webhook routes)
├── config.py                 ← Language config + all prompt text (9 languages)
├── mock_db.py                ← JSON file CRUD helpers
├── generate_prompts.py       ← One-time script to generate all audio prompts
├── services/
│   ├── sarvam_tts.py        ← Sarvam AI TTS API wrapper
│   ├── credit_score.py      ← 300–900 behavioral credit scoring
│   └── financial_ops.py     ← Mock UPI, loan, insurance, savings, PF/NPS
├── tests/
│   ├── test_credit_score.py
│   └── test_financial_ops.py
├── data/
│   ├── users.json
│   ├── accounts.json
│   └── transactions.json
├── prompt_audio/             ← Generated MP3s: {lang}_{prompt}.mp3
├── dynamic_audio/            ← Runtime TTS for amounts/scores
├── requirements.txt
└── .env.example
```

---

## Environment Variables (.env)

```
SARVAM_API_KEY=        # From api.sarvam.ai
TWILIO_ACCOUNT_SID=    # From Twilio console
TWILIO_AUTH_TOKEN=     # From Twilio console
TWILIO_PHONE_NUMBER=   # Your Twilio number (e.g. +12015551234)
SERVER_BASE_URL=       # Your ngrok URL (e.g. https://abc.ngrok.io)
```
