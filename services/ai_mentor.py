import os
from groq import AsyncGroq
from config import LANG_NAMES
from mock_db import get_account, get_user
from services.financial_ops import calculate_behavioral_score

groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

async def get_mentor_response(user_phone: str, user_text: str, lang_key: str) -> str:
    user = await get_user(user_phone)
    acc = await get_account(user['account_id'])
    balance = acc.get('balance', 0)
    score, _ = await calculate_behavioral_score(user_phone)

    lang_name = LANG_NAMES.get(lang_key, "English")

    system_prompt = f"""You are VaaniPay, a helpful and friendly financial advisor for rural Indian users.
- ALWAYS respond ONLY in {lang_name}. Do NOT mix languages.
- Keep responses SHORT: 2-3 simple sentences maximum.
- Use simple, everyday words. No financial jargon.
- Give practical, actionable advice.
- Relate to Indian financial context (UPI, Jan Dhan, PMJBY, SIP, etc.).
- User's current balance: Rs {balance}
- User's credit score: {score}/900
- Be encouraging, warm, and empathetic — you are helping someone who may be new to finance."""

    try:
        response = await groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            temperature=0.7,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"   [LLM EXCEPTION] {e}")
        fallback = {
            "en": "I'm sorry, I could not process that.",
            "hi": "Maafi chahta hoon, mujhe samajh nahi aaya.",
        }
        return fallback.get(lang_key, fallback["en"])
