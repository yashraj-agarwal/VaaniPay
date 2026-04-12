"""
VaaniPay — Audio Prompt Downloader
===================================
Downloads all IVR audio prompts from Sarvam AI TTS and saves them to prompt_audio/.

File naming: prompt_audio/{lang}_{prompt_key}.wav
Example:     prompt_audio/hi_main_menu.wav
             prompt_audio/en_enter_phone.wav

Usage:
    python download_audios.py              # generate all missing files
    python download_audios.py --force      # regenerate everything (overwrite)
    python download_audios.py --lang hi    # only generate Hindi prompts
    python download_audios.py --list       # print all prompt keys without downloading

Set SARVAM_API_KEY in .env before running.
"""

import sys
import argparse
from pathlib import Path
from services.sarvam_tts import save_tts

PROMPT_DIR = Path(__file__).parent / "prompt_audio"

# =============================================================================
# ALL PROMPTS — edit text here to change what Twilio says
# =============================================================================

# The language menu is special: it's played to everyone who calls,
# before they've chosen a language. Each entry plays in its own language
# so the caller hears their own language mentioned.
LANGUAGE_MENU_PROMPTS = {
    # Key: lang_key, Text: what is played (in that language) for the language selection menu
    "en": (
        "Welcome to VaaniPay. Your voice-first financial assistant. "
        "Press 1 for Hindi. "
        "Press 2 for English. "
        "Press 3 for Tamil. "
        "Press 4 for Telugu. "
        "Press 5 for Kannada. "
        "Press 6 for Malayalam. "
        "Press 7 for Marathi. "
        "Press 8 for Bengali. "
        "Press 9 for Gujarati."
    ),
    "hi": "Hindi ke liye 1 dabaye.",
    "ta": "Tamil-il pesave 3 anukku.",
    "te": "Telugu lo matladadam ki 4 nakkandi.",
    "kn": "Kannada dalli maatanadalu 5 alli gothti.",
    "ml": "Malayalam il samsaarikkaan 6 arakkuka.",
    "mr": "Marathi sathi 7 daba.",
    "bn": "Bangla ke liye 8 chapa diye.",
    "gu": "Gujarati mate 9 dabavo.",
}

# Per-language service prompts — played after the caller has chosen their language
SERVICE_PROMPTS = {
    "hi": {
        # Auth
        "enter_phone":      "Kripaya apna 10 ankon ka mobile number darj karein.",
        "enter_mpin":       "Kripaya apna 4 ankon ka mPIN darj karein.",
        "wrong_mpin":       "Galat mPIN. Kripaya punah prayas karein.",
        "mpin_locked":      "Bahut adhik galat prayas. Call samapt ho rahi hai.",
        "no_account":       "Is number par koi khata nahin mila. Dhanyavaad.",
        "auth_success":     "Praamanikaran safal. VaaniPay mein aapka swagat hai.",
        # Main menu
        "main_menu": (
            "Mukhya menu. "
            "UPI bhugtaan ke liye 1 dabayein. "
            "Balance dekhne ke liye 2 dabayein. "
            "Loan ke liye 3 dabayein. "
            "Bima ke liye 4 dabayein. "
            "Credit score ke liye 5 dabayein. "
            "Bachat ke liye 6 dabayein. "
            "PF ya NPS balance ke liye 7 dabayein."
        ),
        # UPI
        "upi_ask_recipient": "Kripaya praaptakarta ka 10 ankon ka mobile number darj karein.",
        "upi_ask_amount":    "Kripaya rakam darj karein, phir hash dabayein.",
        "upi_confirm":       "Bhugtaan ki pushti karne ke liye 1 dabayein, radad karne ke liye 2.",
        "upi_success":       "Bhugtaan safal raha.",
        "upi_failed":        "Bhugtaan vifal. Kripaya punah prayas karein.",
        "upi_not_found":     "Praaptakarta ka khata nahin mila.",
        # Loan
        "loan_not_eligible": "Khed hai. Aapka credit score kam hai. Aap loan ke liye patra nahin hain.",
        "loan_ask_amount":   "Kripaya loan ki rakam darj karein, phir hash dabayein.",
        "loan_confirm":      "Loan ki pushti ke liye 1 dabayein, radad ke liye 2.",
        "loan_approved":     "Loan swikrit. Rakam aapke khate mein jama kar di jayegi.",
        "loan_rejected":     "Aapki patrta ke aadhar par loan aswikrit.",
        # Insurance
        "insurance_menu":    "Bima prakar chunein. Swasthya bima ke liye 1. Durghatna bima ke liye 2. Fasal bima ke liye 3.",
        "insurance_confirm": "Bima sakt karne ke liye 1 dabayein, radad ke liye 2.",
        "insurance_success": "Bima safaltapurvak sakt.",
        # Savings
        "savings_menu":      "Bachat vikalp. Sthir jama ke liye 1. Aavarti jama ke liye 2.",
        "savings_ask_amount": "Kripaya jama rakam darj karein, phir hash dabayein.",
        "savings_ask_duration": "Avadhi mahinon mein darj karein, phir hash dabayein.",
        "savings_confirm":    "Jama ki pushti ke liye 1 dabayein.",
        "savings_success":    "Jama safaltapurvak darj.",
        # General
        "invalid":           "Amanya input. Kripaya punah prayas karein.",
        "goodbye":           "VaaniPay ka upyog karne ke liye dhanyavaad. Namaste.",
        "error":             "Tantrik samasya. Kripaya baad mein prayas karein.",
        "please_wait":       "Kripaya prateeksha karein.",
    },

    "en": {
        "enter_phone":      "Please enter your 10-digit mobile number.",
        "enter_mpin":       "Please enter your 4-digit mPIN.",
        "wrong_mpin":       "Incorrect mPIN. Please try again.",
        "mpin_locked":      "Too many failed attempts. Ending call.",
        "no_account":       "No account found for this number. Thank you.",
        "auth_success":     "Authentication successful. Welcome to VaaniPay.",
        "main_menu": (
            "Main menu. "
            "Press 1 for UPI payment. "
            "Press 2 for balance. "
            "Press 3 for loan. "
            "Press 4 for insurance. "
            "Press 5 for credit score. "
            "Press 6 for savings. "
            "Press 7 for PF or NPS balance."
        ),
        "upi_ask_recipient": "Please enter the recipient's 10-digit mobile number.",
        "upi_ask_amount":    "Please enter the amount, then press hash.",
        "upi_confirm":       "Press 1 to confirm payment, press 2 to cancel.",
        "upi_success":       "Payment successful.",
        "upi_failed":        "Payment failed. Please try again.",
        "upi_not_found":     "Recipient account not found.",
        "loan_not_eligible": "Sorry, your credit score is too low. You are not eligible for a loan.",
        "loan_ask_amount":   "Please enter the loan amount, then press hash.",
        "loan_confirm":      "Press 1 to confirm loan, press 2 to cancel.",
        "loan_approved":     "Loan approved. Amount will be credited to your account.",
        "loan_rejected":     "Loan rejected based on your eligibility.",
        "insurance_menu":    "Choose insurance type. Press 1 for health insurance. Press 2 for accident insurance. Press 3 for crop insurance.",
        "insurance_confirm": "Press 1 to activate insurance, press 2 to cancel.",
        "insurance_success": "Insurance activated successfully.",
        "savings_menu":      "Savings options. Press 1 for Fixed Deposit. Press 2 for Recurring Deposit.",
        "savings_ask_amount": "Please enter the deposit amount, then press hash.",
        "savings_ask_duration": "Enter duration in months, then press hash.",
        "savings_confirm":    "Press 1 to confirm deposit.",
        "savings_success":    "Deposit recorded successfully.",
        "invalid":           "Invalid input. Please try again.",
        "goodbye":           "Thank you for using VaaniPay. Goodbye.",
        "error":             "Technical error. Please try again later.",
        "please_wait":       "Please wait.",
    },

    "ta": {
        "enter_phone":      "Ungal 10 ilakkam mobile enai ullidavum.",
        "enter_mpin":       "Ungal 4 ilakkam mPIN ullidavum.",
        "wrong_mpin":       "Thappaana mPIN. Meendum muyandrukavum.",
        "mpin_locked":      "Adhiga tholvigal. Azhaippu niruththappadukiradhu.",
        "no_account":       "Intha numberi kanakku illai.",
        "auth_success":     "Saandru unarpagam vetrrikaramaanavadhu. VaaniPay-il varavERppu.",
        "main_menu":        "Mookkiya menu. UPI seluththal 1. Nilai 2. Kadan 3. Kaappu 4. Credit score 5. Semipu 6. PF alladu NPS 7.",
        "upi_ask_recipient": "Petralaar 10 ilakkam enai ullidavum.",
        "upi_ask_amount":    "Thokai ullidunga, hash anukku.",
        "upi_confirm":       "Seluththal uruthi 1, raddu 2.",
        "upi_success":       "Seluththal vetrrikaramaanavadhu.",
        "upi_failed":        "Seluththal tholviyuriyadhu.",
        "upi_not_found":     "Petralaar kanakku illai.",
        "loan_not_eligible": "Manikavum, neengal kadanukku thagudhi illai.",
        "loan_ask_amount":   "Kadan thokai ullidunga, hash anukku.",
        "loan_confirm":      "Kadan uruthi 1, raddu 2.",
        "loan_approved":     "Kadan anumathikkappattathu.",
        "loan_rejected":     "Kadan nirakkarikkappattathu.",
        "insurance_menu":    "Kaappu vagaippai thervusei. 1 udalnaalam, 2 viduppattu, 3 payan.",
        "insurance_confirm": "Kaappu seyal 1, raddu 2.",
        "insurance_success": "Kaappu seyyappattathu.",
        "savings_menu":      "Semipu. 1 niraiya vaipu, 2 thozharvu vaipu.",
        "savings_ask_amount": "Vaipu thokai ullidunga, hash anukku.",
        "savings_ask_duration": "Maadangalil kaalam ullidunga, hash anukku.",
        "savings_confirm":    "Uruthi 1.",
        "savings_success":    "Vaipu pathivu seyyappattathu.",
        "invalid":           "Thappaana ullidai.",
        "goodbye":           "VaaniPay payanpaduttiyatharku nandri.",
        "error":             "Thazhnilai pazhuthu.",
        "please_wait":       "Thayavuseitu kaattirunga.",
    },

    "te": {
        "enter_phone":      "Meeru 10 ankela mobile number namoodu cheyandi.",
        "enter_mpin":       "Meeru 4 ankela mPIN namoodu cheyandi.",
        "wrong_mpin":       "Thappu mPIN. Meeru malli prayancinandi.",
        "mpin_locked":      "Ekkuva viphala prayanalu. Call muginipotundi.",
        "no_account":       "Ee numberu lo khaata ledu.",
        "auth_success":     "Dharuveekarana vijayavantamindi. VaaniPay ki swaagatam.",
        "main_menu":        "Pradhana menu. UPI chellimpu 1. Balansu 2. Runam 3. Bheema 4. Credit score 5. Podupulu 6. PF ledu NPS 7.",
        "upi_ask_recipient": "Graheeta 10 ankela number namoodu cheyandi.",
        "upi_ask_amount":    "Mottam namoodu chesi hash nakkandi.",
        "upi_confirm":       "Nirdharinchate 1, raddu 2.",
        "upi_success":       "Chellimpu vijayavantamindi.",
        "upi_failed":        "Chellimpu viphalamaindi.",
        "upi_not_found":     "Graheeta khaata kanugonabadaledu.",
        "loan_not_eligible": "Ksaminchandi, meeru runaniki arhulu kaadu.",
        "loan_ask_amount":   "Runam mottam namoodu chesi hash nakkandi.",
        "loan_confirm":      "Runam nirdharana 1, raddu 2.",
        "loan_approved":     "Runam manjuruaindi.",
        "loan_rejected":     "Runam thiraskarinchababaindi.",
        "insurance_menu":    "Bheema rakaamu. 1 Aarogyam, 2 Pramaadam, 3 Pandlu.",
        "insurance_confirm": "Bheema sakriyam 1, raddu 2.",
        "insurance_success": "Bheema sakriyamindi.",
        "savings_menu":      "Podupulu. 1 Sthira Deposit, 2 Punareeksha Deposit.",
        "savings_ask_amount": "Mottam namoodu chesi hash nakkandi.",
        "savings_ask_duration": "Nelallo kaalaavadhi namoodu chesi hash nakkandi.",
        "savings_confirm":    "Nirdharinchate 1.",
        "savings_success":    "Deposit nondaindi.",
        "invalid":           "Chaellani input.",
        "goodbye":           "VaaniPay upayoginchinduku dhanyavaadaalu.",
        "error":             "Sangeetika paatha.",
        "please_wait":       "Dayachesi veechinchandi.",
    },

    "kn": {
        "enter_phone":      "Nimma 10 ankiya mobile sankhye namoodisi.",
        "enter_mpin":       "Nimma 4 ankiya mPIN namoodisi.",
        "wrong_mpin":       "Tappu mPIN. Matte prayathnisi.",
        "mpin_locked":      "Hechu tappu prayathnagalu. Kare mugiyuttide.",
        "no_account":       "Ee sankhyege khate illa.",
        "auth_success":     "Pramaanikarana yashashvi. VaaniPay ge swagata.",
        "main_menu":        "Mukhya menu. UPI pavathi 1. Shalku 2. Sala 3. Vime 4. Credit score 5. Ulitaaya 6. PF athava NPS 7.",
        "upi_ask_recipient": "Sveekarisi taakiya 10 ankiya sankhye namoodisi.",
        "upi_ask_amount":    "Motta namoodisi, hash ottiri.",
        "upi_confirm":       "Dhrudheekarisalu 1, raddu 2.",
        "upi_success":       "Pavathi yashashvi.",
        "upi_failed":        "Pavathi viphala.",
        "upi_not_found":     "Sveekarisi taakaravara khate illa.",
        "loan_not_eligible": "Kshamisi, neevu salanukke arhavagilla.",
        "loan_ask_amount":   "Sala motta namoodisi, hash ottiri.",
        "loan_confirm":      "Sala dhrudheekarana 1, raddu 2.",
        "loan_approved":     "Sala anumodita.",
        "loan_rejected":     "Sala nirasita.",
        "insurance_menu":    "Vime prakaara. 1 Aarogyam, 2 Apaghaata, 3 Beralu.",
        "insurance_confirm": "Vime sakraya 1, raddu 2.",
        "insurance_success": "Vime sakrayagide.",
        "savings_menu":      "Ulitaaya. 1 Sthira Vandana, 2 Aavrtti Vandana.",
        "savings_ask_amount": "Motta namoodisi, hash ottiri.",
        "savings_ask_duration": "Tingaligalalli avadhi namoodisi, hash ottiri.",
        "savings_confirm":    "Dhrudheekarisalu 1.",
        "savings_success":    "Vandana daakhala.",
        "invalid":           "Amanya input.",
        "goodbye":           "VaaniPay balasi dhannavada.",
        "error":             "Tantrika doorti.",
        "please_wait":       "Dayavittu neeredisi.",
    },

    "ml": {
        "enter_phone":      "Ninnude 10 akkamulla mobile number nalkuka.",
        "enter_mpin":       "Ninnude 4 akkamulla mPIN nalkuka.",
        "wrong_mpin":       "Theettaya mPIN. Vendum shreemikuka.",
        "mpin_locked":      "Eera parichodhanagal adhikamaayi. Kol avasaanikkunnu.",
        "no_account":       "Ee numberin account kaanikkunilla.",
        "auth_success":     "Pramaanikaranam vijayakaram. VaaniPay-il swaagatam.",
        "main_menu":        "Pradhana menu. UPI payment 1. Balance 2. Loan 3. Insurance 4. Credit score 5. Savings 6. PF allenkil NPS 7.",
        "upi_ask_recipient": "Sveekartavante 10 akkamulla number nalkuka.",
        "upi_ask_amount":    "Thukaanu nalkuka, pin hash arakkuka.",
        "upi_confirm":       "Sthirikarikkan 1, raddu 2.",
        "upi_success":       "Payment vijayakaram.",
        "upi_failed":        "Payment parajayapettu.",
        "upi_not_found":     "Sveekartavante account kaanikunilla.",
        "loan_not_eligible": "Kshamikkanam, neenga loan-inu yogyaralla.",
        "loan_ask_amount":   "Loan thukaanu nalkuka, hash arakkuka.",
        "loan_confirm":      "Loan sthireekaranam 1, raddu 2.",
        "loan_approved":     "Loan anumathicha.",
        "loan_rejected":     "Loan nirasichchi.",
        "insurance_menu":    "Insurance tharam. 1 Aarogyam, 2 Aapaddhu, 3 Velam.",
        "insurance_confirm": "Insurance pravarthanam 1, raddu 2.",
        "insurance_success": "Insurance pravarthanam vijayakaram.",
        "savings_menu":      "Savings. 1 Fixed Deposit, 2 Recurring Deposit.",
        "savings_ask_amount": "Thukaanu nalkuka, hash arakkuka.",
        "savings_ask_duration": "Maasangalil kaalavadhi nalkuka, hash arakkuka.",
        "savings_confirm":    "Sthireekarikkan 1.",
        "savings_success":    "Deposit rekha.",
        "invalid":           "Asaadhu input.",
        "goodbye":           "VaaniPay upayogichathin nandhi.",
        "error":             "Samperka pathivu.",
        "please_wait":       "Dayavaayi kaathu nilkkuka.",
    },

    "mr": {
        "enter_phone":      "Krupaya tumcha 10 anki mobile number pravesh kara.",
        "enter_mpin":       "Krupaya tumcha 4 anki mPIN pravesh kara.",
        "wrong_mpin":       "Chukicha mPIN. Punha prayas kara.",
        "mpin_locked":      "Jast chukiche prayas. Call sampat ahe.",
        "no_account":       "Ya numbervara khate aadhal naahi.",
        "auth_success":     "Pramineekarana yashashvi. VaaniPay madhye svagat.",
        "main_menu":        "Mukhya menu. UPI deykasathi 1. Shilakaasathi 2. Karja sathi 3. Vimyasathi 4. Credit score sathi 5. Bachatsathi 6. PF kinva NPS sathi 7.",
        "upi_ask_recipient": "Praptakartyacha 10 anki number pravesh kara.",
        "upi_ask_amount":    "Rakam pravesh kara, mag hash daba.",
        "upi_confirm":       "Deyk pustikarat 1, radda 2.",
        "upi_success":       "Deyk yashashvi.",
        "upi_failed":        "Deyk apayashi.",
        "upi_not_found":     "Praptakartyache khate sapadal naahi.",
        "loan_not_eligible": "Maaf kara, tum karja sathi patra naahit.",
        "loan_ask_amount":   "Karja rakam pravesh kara, hash daba.",
        "loan_confirm":      "Karja pustikaran 1, radda 2.",
        "loan_approved":     "Karja manjur.",
        "loan_rejected":     "Karja nakar.",
        "insurance_menu":    "Vima prakar. 1 Aarogya, 2 Apghaat, 3 Peek.",
        "insurance_confirm": "Vima sakriya 1, radda 2.",
        "insurance_success": "Vima yashashviri ta sakriya.",
        "savings_menu":      "Bachat vikalp. 1 Mudat thev, 2 Aavrti thev.",
        "savings_ask_amount": "Rakam pravesh kara, hash daba.",
        "savings_ask_duration": "Mahinyanmadhe avadhi pravesh kara, hash daba.",
        "savings_confirm":    "Pustikaran sathi 1.",
        "savings_success":    "Thev nondvali.",
        "invalid":           "Ayogya input.",
        "goodbye":           "VaaniPay vaparlyas abhar.",
        "error":             "Tantrik samasya.",
        "please_wait":       "Krupaya pratiksha kara.",
    },

    "bn": {
        "enter_phone":      "Apnar 10 sankhyar mobile number diun.",
        "enter_mpin":       "Apnar 4 sankhyar mPIN diun.",
        "wrong_mpin":       "Bhul mPIN. Abar cheshta korun.",
        "mpin_locked":      "Onek bhul cheshta. Call shesh hochche.",
        "no_account":       "Ei numbere kono account paoa jaaini.",
        "auth_success":     "Pramanikaran safal. VaaniPay-e swagato.",
        "main_menu":        "Mukhya menu. UPI payment 1. Balance 2. Rin 3. Bima 4. Credit score 5. Shanchoye 6. PF ba NPS 7.",
        "upi_ask_recipient": "Grahakero 10 sankhyar number diun.",
        "upi_ask_amount":    "Parimaan diun, tokhon hash chapa diye.",
        "upi_confirm":       "Payment nishchit 1, raddo 2.",
        "upi_success":       "Payment safal.",
        "upi_failed":        "Payment biph al.",
        "upi_not_found":     "Grahakero account paoa jaaini.",
        "loan_not_eligible": "Dukkhit, aapni rin paaoar janya jogyo na.",
        "loan_ask_amount":   "Rin parimaan diun, hash chapa diye.",
        "loan_confirm":      "Rin nishchintokaari 1, raddo 2.",
        "loan_approved":     "Rin anumodit.",
        "loan_rejected":     "Rin prakhya anit.",
        "insurance_menu":    "Bima prakar. 1 Swasthya, 2 Durghothna, 3 Fasal.",
        "insurance_confirm": "Bima saktiya 1, raddo 2.",
        "insurance_success": "Bima safalbhabe saktiya.",
        "savings_menu":      "Shanchoy. 1 Sthira Amaanat, 2 Punoravritti Amaanat.",
        "savings_ask_amount": "Parimaan diun, hash chapa diye.",
        "savings_ask_duration": "Maasey kaaalkaal diun, hash chapa diye.",
        "savings_confirm":    "Nishchit 1.",
        "savings_success":    "Amaanat nathivukt.",
        "invalid":           "Baidho input.",
        "goodbye":           "VaaniPay baybaharer jonyo dhanyabaad.",
        "error":             "Tantrik samasya.",
        "please_wait":       "Doyakore apekkhaa korun.",
    },

    "gu": {
        "enter_phone":      "Krupa karine tamaro 10 anko no mobile number darj karo.",
        "enter_mpin":       "Krupa karine tamaro 4 anko no mPIN darj karo.",
        "wrong_mpin":       "Khoṭo mPIN. Pharthi prayas karo.",
        "mpin_locked":      "Ghano khoṭa prayaso. Kol paṭo thaay che.",
        "no_account":       "Aa number par khatu malyu nathi.",
        "auth_success":     "Pramanikaran saphal. VaaniPay ma aapnu swagat che.",
        "main_menu":        "Mukhy menu. UPI chukvani 1. Balance 2. Loan 3. Vima 4. Credit score 5. Bachat 6. PF athava NPS 7.",
        "upi_ask_recipient": "Melo sautano 10 anko no number darj karo.",
        "upi_ask_amount":    "Rakam darj karo, pachhi hash dabavo.",
        "upi_confirm":       "Chukvani ni pushti 1, raddo 2.",
        "upi_success":       "Chukvani saphal.",
        "upi_failed":        "Chukvani niphal.",
        "upi_not_found":     "Melo sutano khatu malyu nathi.",
        "loan_not_eligible": "Maaf karo, tame loan mate layak nathi.",
        "loan_ask_amount":   "Loan ni rakam darj karo, hash dabavo.",
        "loan_confirm":      "Loan ni pushti 1, raddo 2.",
        "loan_approved":     "Loan manjur.",
        "loan_rejected":     "Loan nakaru.",
        "insurance_menu":    "Vima prakar. 1 Swasthya, 2 Aapatti, 3 Pako.",
        "insurance_confirm": "Vima sakriya 1, raddo 2.",
        "insurance_success": "Vima saphal rite sakriya.",
        "savings_menu":      "Bachat vikalpo. 1 Sthir Thapan, 2 Punaravrti Thapan.",
        "savings_ask_amount": "Rakam darj karo, hash dabavo.",
        "savings_ask_duration": "Mahinaama gaalo darj karo, hash dabavo.",
        "savings_confirm":    "Pushti mate 1.",
        "savings_success":    "Thapan nondhayu.",
        "invalid":           "Amanya input.",
        "goodbye":           "VaaniPay vaapravaa badal aabhar.",
        "error":             "Tantrik samasya.",
        "please_wait":       "Krupa karine raho.",
    },
}


# =============================================================================
# DOWNLOAD LOGIC
# =============================================================================

def download_language_menus(force: bool = False) -> tuple[int, int]:
    """Download the per-language menu snippets (played before language is chosen)."""
    ok = 0
    fail = 0
    print("\n=== Language Selection Menu Prompts ===")
    for lang_key, text in LANGUAGE_MENU_PROMPTS.items():
        out_path = PROMPT_DIR / f"{lang_key}_lang_menu.wav"
        if out_path.exists() and not force:
            print(f"  SKIP (exists): {out_path.name}")
            ok += 1
            continue
        print(f"  Generating: {out_path.name} ...", end=" ", flush=True)
        if save_tts(text, lang_key, out_path):
            print("OK")
            ok += 1
        else:
            print("FAIL")
            fail += 1
    return ok, fail


def download_service_prompts(force: bool = False, lang_filter: str | None = None) -> tuple[int, int]:
    """Download all per-language service prompts."""
    ok = 0
    fail = 0
    langs = [lang_filter] if lang_filter else list(SERVICE_PROMPTS.keys())

    for lang_key in langs:
        prompts = SERVICE_PROMPTS.get(lang_key)
        if not prompts:
            print(f"\n  WARNING: no prompts defined for lang '{lang_key}'")
            continue

        print(f"\n=== [{lang_key}] Service Prompts ===")
        for prompt_key, text in prompts.items():
            out_path = PROMPT_DIR / f"{lang_key}_{prompt_key}.wav"
            if out_path.exists() and not force:
                print(f"  SKIP (exists): {out_path.name}")
                ok += 1
                continue
            print(f"  Generating: {out_path.name} ...", end=" ", flush=True)
            if save_tts(text, lang_key, out_path):
                print("OK")
                ok += 1
            else:
                print("FAIL")
                fail += 1

    return ok, fail


def main():
    parser = argparse.ArgumentParser(description="Download VaaniPay IVR audio prompts via Sarvam AI TTS")
    parser.add_argument("--force",  action="store_true", help="Regenerate even if file already exists")
    parser.add_argument("--lang",   type=str, default=None, help="Only generate for one language (e.g. --lang hi)")
    parser.add_argument("--list",   action="store_true", help="Print all prompt keys without downloading")
    args = parser.parse_args()

    if args.list:
        print("\nLanguage menu prompts:")
        for lang_key in LANGUAGE_MENU_PROMPTS:
            print(f"  prompt_audio/{lang_key}_lang_menu.wav")
        print("\nService prompts:")
        for lang_key, prompts in SERVICE_PROMPTS.items():
            for key in prompts:
                print(f"  prompt_audio/{lang_key}_{key}.wav")
        total = len(LANGUAGE_MENU_PROMPTS) + sum(len(v) for v in SERVICE_PROMPTS.values())
        print(f"\nTotal: {total} files")
        return

    PROMPT_DIR.mkdir(exist_ok=True)

    total_ok = 0
    total_fail = 0

    if not args.lang:
        ok, fail = download_language_menus(force=args.force)
        total_ok += ok
        total_fail += fail

    ok, fail = download_service_prompts(force=args.force, lang_filter=args.lang)
    total_ok += ok
    total_fail += fail

    print(f"\n{'='*50}")
    print(f"Done: {total_ok} succeeded, {total_fail} failed")
    if total_fail > 0:
        print("Re-run to retry failed files (skips already-downloaded ones automatically).")


if __name__ == "__main__":
    main()
