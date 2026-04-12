# ============================
#  SERVER.PY (UNIFIED BACKEND)
#  PART 1 OF 4
# ============================

import requests
import os
import io
import json
import base64
import time
from pathlib import Path
from threading import Thread

from flask import Flask, request, jsonify, Response, send_from_directory

# AES Encryption
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# Google Cloud Clients
from google.cloud import documentai_v1 as documentai
from google.cloud import texttospeech_v1 as texttospeech
from google.protobuf.json_format import MessageToDict

# LLM Client (OpenAI)
from openai import OpenAI

# Image → PDF helper
from PIL import Image

# Load environment
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# ====================================================================
# PATHS & DIRECTORIES
# ====================================================================

BASE_DIR = Path(__file__).parent
PROMPT_DIR = BASE_DIR / "prompt_audio"
MOCK_DB_PATH = BASE_DIR / "mock_db.json"

# Where we store Twilio call state per CallSid
CALL_STATE = {}

# Where we store summary generation state during a Twilio call
SUMMARY_STATE = {
    "busy": False,
    "ready": False,
    "audio_path": None,
    "text": None,
}

# Allow Flutter app override via .env
SERVER_BASE = os.getenv("SERVER_BASE_URL")
if not SERVER_BASE:
    SERVER_BASE = None  # falls back to request.url_root later

# ====================================================================
#  AUDIO PROMPTS (New naming convention: {lang_key}_{prompt}.mp3)
# ====================================================================

LANG_CONFIG = {
    "1": {"lang_key": "en", "tts_lang": "en-IN"},
    "2": {"lang_key": "hi", "tts_lang": "hi-IN"},
    "3": {"lang_key": "bn", "tts_lang": "bn-IN"},
    "4": {"lang_key": "te", "tts_lang": "te-IN"},
    "5": {"lang_key": "mr", "tts_lang": "mr-IN"},
    "6": {"lang_key": "ta", "tts_lang": "ta-IN"},
    "7": {"lang_key": "gu", "tts_lang": "gu-IN"},
    "8": {"lang_key": "kn", "tts_lang": "kn-IN"},
    "9": {"lang_key": "ml", "tts_lang": "ml-IN"},
}

# Every prompt name we expect for each lang_key
PROMPTS = [
    "menu_intro",
    "menu_lang",                    # no number suffix anymore
    "ask_name",
    "ask_aadhaar",
    "aadhaar_too_short",
    "ask_if_want_to_explain_source",
    "could_not_hear_name_try_again",
    "did_not_receive_aadhaar_try",
    "did_not_receive_name_try_one_more_time",
    "error_generating",
    "invalid_selection",
    "no_input_detected_goodbye",
    "no_input",
    "notice_not_readable",
    "please_wait_summary",
    "sorry_not_found",
    "still_no_aadhaar_goodbye",
    "still_no_name_continue_without",
    "thanks_we_will_try_search_call_back",
]

def audio_file(lang_key: str, prompt: str) -> str:
    """
    Resolve audio prompt path using your exact naming convention:
    {lang_key}_{prompt}.mp3
    """
    filename = f"{lang_key}_{prompt}.mp3"
    return f"/audio/{filename}"

def load_mock_db():
    """
    Loads the mock database from mock_db.json.
    Expected format:
    {
        "123412341234": {
            "notice": "Full notice text here"
        },
        "987698769876": {
            "notice": "Some other notice text"
        }
    }
    """
    if not MOCK_DB_PATH.exists():
        print("⚠️ mock_db.json not found — creating an empty one.")
        with open(MOCK_DB_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)
        return {}

    try:
        with open(MOCK_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("❌ ERROR reading mock_db.json:", e)
        return {}


# ====================================================================
#  GOOGLE CLOUD CREDENTIALS
# ====================================================================

gcred = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if gcred:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = gcred

PROJECT_ID = os.getenv("DOCUMENT_AI_PROJECT_ID")
LOCATION = os.getenv("DOCUMENT_AI_LOCATION", "us")
PROCESSOR_ID = os.getenv("DOCUMENT_AI_PROCESSOR_ID")

if not PROJECT_ID or not PROCESSOR_ID:
    raise RuntimeError("Missing Document AI env vars")

docai_client = documentai.DocumentProcessorServiceClient()
PROCESSOR_NAME = docai_client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

# ====================================================================
#  AES-256 ENCRYPTION CONFIG
# ====================================================================

ENCRYPTION_KEY_BASE64 = os.getenv("ENCRYPTION_KEY_BASE64")
if not ENCRYPTION_KEY_BASE64:
    raise RuntimeError("Missing ENCRYPTION_KEY_BASE64 in .env")

KEY_BYTES = base64.b64decode(ENCRYPTION_KEY_BASE64)

def decrypt_bytes(cipher_b64: str, iv_b64: str) -> bytes:
    """
    AES/CBC decrypt from Flutter app input.
    """
    cipher_bytes = base64.b64decode(cipher_b64)
    iv = base64.b64decode(iv_b64)

    cipher = AES.new(KEY_BYTES, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(cipher_bytes)

    try:
        return unpad(decrypted, AES.block_size)
    except ValueError:
        print("Padding error during decrypt.")
        raise

def encrypt_bytes(plaintext: bytes) -> dict:
    """
    AES/CBC encrypt for sending back to Flutter.
    """
    iv = os.urandom(16)
    cipher = AES.new(KEY_BYTES, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(pad(plaintext, AES.block_size))
    return {
        "iv": base64.b64encode(iv).decode("utf-8"),
        "data": base64.b64encode(ciphertext).decode("utf-8"),
    }

# ====================================================================
#  OCR HELPERS (Document AI)
# ====================================================================

def images_to_pdf_bytes(images: list[bytes]) -> bytes:
    """
    Convert a list of raw image bytes into a single PDF.
    """
    pil_images = [Image.open(io.BytesIO(img)).convert("RGB") for img in images]
    output = io.BytesIO()
    pil_images[0].save(output, format="PDF", save_all=True, append_images=pil_images[1:])
    return output.getvalue()

def call_document_ai(document_bytes: bytes, mime_type="application/pdf"):
    """
    Send PDF to Google Document AI and extract text + full JSON structure.
    """
    raw_document = documentai.RawDocument(content=document_bytes, mime_type=mime_type)

    result = docai_client.process_document(
        request={"name": PROCESSOR_NAME, "raw_document": raw_document}
    )
    document = result.document
    doc_dict = MessageToDict(document._pb, preserving_proto_field_name=True)
    doc_text = document.text or ""

    return doc_dict, doc_text

# ====================================================================
#  OPENAI SUMMARIZER (LLM)
# ====================================================================

llm = OpenAI()

SUMMARY_SYSTEM_PROMPT = """
You are an assistant that explains official notices/documents to users in simple language.

Return JSON WITH THIS EXACT STRUCTURE:

{
 "title": "short 5–8 word title",
 "explanation": "long explanation suitable for TTS",
 "actions": "step-by-step actions the user must take"
}

The explanation must be structured, clear, and friendly.
""".strip()

def summarize_with_llm(doc_text: str, language_name: str) -> tuple[str, str]:
    """
    Produces:
    - title
    - combined explanation + actions
    """

    # Reduce text if necessary
    if len(doc_text) > 20000:
        doc_text = doc_text[:20000]

    user_prompt = f"""
User prefers explanation in language: {language_name}

Recognized Document Text:
{doc_text}

Return the JSON only.
""".strip()

    resp = llm.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1000,
        temperature=0.3,
    )

    content = resp.choices[0].message.content.strip()

    try:
        data = json.loads(content)
        title = data.get("title", "").strip()
        explanation = data.get("explanation", "").strip()
        actions = data.get("actions", "").strip()
    except Exception:
        # Fallback if JSON parse fails
        title = "Document Summary"
        explanation = doc_text[:1500]
        actions = ""

    combined = explanation
    if actions:
        combined += "\n\nActionable Steps:\n" + actions

    return title, combined

# ====================================================================
#  GOOGLE TTS: Multi-language voices
# ====================================================================

tts_client = texttospeech.TextToSpeechClient()

LANGUAGE_TO_TTS = {
    "english": "en-IN",
    "hindi": "hi-IN",
    "bangla": "bn-IN",
    "bengali": "bn-IN",
    "gujarati": "gu-IN",
    "marathi": "mr-IN",
    "tamil": "ta-IN",
    "telugu": "te-IN",
    "kannada": "kn-IN",
    "malayalam": "ml-IN",
}

def resolve_tts_language(language_name: str) -> str:
    key = (language_name or "").strip().lower()
    return LANGUAGE_TO_TTS.get(key, "en-IN")

def generate_tts(text: str, language_name: str) -> bytes:
    lang_code = resolve_tts_language(language_name)

    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(language_code=lang_code)
    audio_cfg = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

    response = tts_client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_cfg,
    )
    return response.audio_content

# ============================
#  SERVER.PY — PART 2 OF 4
#  FLUTTER DOCUMENT PIPELINE
# ============================

# ====================================================================
#  ENDPOINT: /process-document
#  (Used by FLUTTER app)
# ====================================================================
@app.route("/process-document", methods=["POST"])
def process_document():
    """
    Flutter sends:
    {
        "type": "pdf" or "images",
        "language": "Hindi" etc,
        "quality": "fast" or "high",
        "iv": "...", "data": "...",   // for PDF
        "files": [ {iv, data}, ... ]   // for images
    }
    Returns encrypted title + summary + (optional) encrypted TTS audio.
    """

    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    if not data or "type" not in data:
        return jsonify({"error": "Missing type"}), 400

    doc_type = data["type"]
    language_name = data.get("language", "English")
    quality = data.get("quality", "high")

    try:
        # ---------------------------------------------
        # CASE 1: PDF
        # ---------------------------------------------
        if doc_type == "pdf":
            iv_b64 = data["iv"]
            cipher_b64 = data["data"]
            pdf_bytes = decrypt_bytes(cipher_b64, iv_b64)

            doc_dict, doc_text = call_document_ai(pdf_bytes)

        # ---------------------------------------------
        # CASE 2: IMAGES → convert to PDF
        # ---------------------------------------------
        elif doc_type == "images":
            images = data.get("files", [])
            if not images:
                return jsonify({"error": "No image files provided"}), 400

            img_bytes_list = []
            for f in images:
                iv_b64 = f["iv"]
                cipher_b64 = f["data"]
                img_bytes = decrypt_bytes(cipher_b64, iv_b64)
                img_bytes_list.append(img_bytes)

            pdf_bytes = images_to_pdf_bytes(img_bytes_list)

            doc_dict, doc_text = call_document_ai(pdf_bytes)

        else:
            return jsonify({"error": f"Unknown document type: {doc_type}"}), 400

        # -----------------------------------------------------------
        # SAVE raw DocumentAI output (debugging)
        # -----------------------------------------------------------
        out_json = BASE_DIR / "last_result.json"
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(doc_dict, f, indent=2, ensure_ascii=False)

        # -----------------------------------------------------------
        # LLM SUMMARY
        # -----------------------------------------------------------
        title, combined_text = summarize_with_llm(doc_text, language_name)

        # Save text summary
        out_txt = BASE_DIR / "last_summary.txt"
        with open(out_txt, "w", encoding="utf-8") as f:
            f.write(combined_text)

        # -----------------------------------------------------------
        # Encrypt title + summary
        # -----------------------------------------------------------
        enc_title = encrypt_bytes(title.encode("utf-8"))
        enc_summary = encrypt_bytes(combined_text.encode("utf-8"))

        # -----------------------------------------------------------
        # QUALITY MODE DECISION
        # -----------------------------------------------------------
        if quality == "high":
            try:
                audio_bytes = generate_tts(combined_text, language_name)
                enc_audio = encrypt_bytes(audio_bytes)

                return jsonify({
                    "status": "ok",
                    "quality": "high",
                    "title_iv": enc_title["iv"],
                    "title_data": enc_title["data"],
                    "summary_iv": enc_summary["iv"],
                    "summary_data": enc_summary["data"],
                    "audio_iv": enc_audio["iv"],
                    "audio_data": enc_audio["data"],
                }), 200

            except Exception as e:
                # fallback to fast mode
                print("TTS ERROR → Falling back:", repr(e))

        # FAST MODE RESPONSE
        return jsonify({
            "status": "ok",
            "quality": "fast",
            "title_iv": enc_title["iv"],
            "title_data": enc_title["data"],
            "summary_iv": enc_summary["iv"],
            "summary_data": enc_summary["data"],
        }), 200

    except Exception as e:
        print("ERROR IN /process-document:", e)
        return jsonify({"error": "Processing failed", "details": str(e)}), 500



# ====================================================================
#  TWILIO ENDPOINT: /generate_explanation (for IVR)
# ====================================================================
@app.route("/generate_explanation", methods=["POST"])
def generate_explanation():
    """
    Twilio calls this asynchronously in background:
    {
        "text": "... notice text ...",
        "language": "Hindi",
        "quality": "high"
    }
    It prepares MP3 summary and stores path for /poll-summary
    """

    if SUMMARY_STATE["busy"]:
        return jsonify({"status": "busy"}), 409

    payload = request.get_json(force=True)
    doc_text = payload.get("text", "")
    language_name = payload.get("language", "English")
    quality = payload.get("quality", "high")

    # Mark busy
    SUMMARY_STATE["busy"] = True
    SUMMARY_STATE["ready"] = False
    SUMMARY_STATE["audio_path"] = None
    SUMMARY_STATE["text"] = None

    def worker():
        try:
            # ---------------------------
            # 1. LLM Summary
            # ---------------------------
            title, combined_text = summarize_with_llm(doc_text, language_name)

            SUMMARY_STATE["text"] = combined_text

            # ---------------------------
            # 2. TTS
            # ---------------------------
            if quality == "high":
                try:
                    audio_bytes = generate_tts(combined_text, language_name)

                    audio_path = BASE_DIR / "summary_audio.mp3"
                    with open(audio_path, "wb") as f:
                        f.write(audio_bytes)

                    SUMMARY_STATE["audio_path"] = str(audio_path)

                except Exception as e:
                    print("TTS FAILED IN THREAD:", e)

            SUMMARY_STATE["ready"] = True

        finally:
            SUMMARY_STATE["busy"] = False

    # Run async thread
    Thread(target=worker, daemon=True).start()

    return jsonify({"status": "started"}), 200



# ====================================================================
# POLLING ENDPOINT FOR TWILIO
# ====================================================================
@app.route("/poll-summary", methods=["POST"])
def poll_summary():
    """
    Twilio calls this every 3 seconds:
    -> Returns audio_url when ready
    """

    if SUMMARY_STATE.get("ready"):
        audio_path = SUMMARY_STATE.get("audio_path")
        text = SUMMARY_STATE.get("text", "")

        if audio_path:
            filename = os.path.basename(audio_path)
            audio_url = f"/summary-audio/{filename}"

            return jsonify({
                "ready": True,
                "has_audio": True,
                "audio_url": audio_url,
                "text": text,
            })

        else:
            # TTS failed → fallback to text
            return jsonify({
                "ready": True,
                "has_audio": False,
                "text": text,
            })

    return jsonify({"ready": False}), 200

# ====================================================================
# STATIC SERVE SUMMARY AUDIO FILES
# ====================================================================
def play_prompt(lang_key: str, prompt: str) -> str:
    """Return the correct <Play> tag for a prompt MP3."""
    filename = f"{lang_key}_{prompt}.mp3"
    return f"<Play>/audio/{filename}</Play>"


# ------------------------------------------------------
# 1) ENTRYPOINT — PLAY LANGUAGE MENU
# ------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def voice_entry():
    call_sid = request.form.get("CallSid", "")
    CALL_STATE[call_sid] = {"attempts": 0}

    # Plays: {lang}_menu_intro.mp3 then gather 1–9 input
    twiml = f"""
    <Response>
        <Gather input="dtmf" numDigits="1" timeout="8" action="/handle-language" method="POST">
            {play_prompt("en", "menu_intro")}
            {play_prompt("en", "menu_lang")}
            {play_prompt("hi", "menu_lang")}
            {play_prompt("bn", "menu_lang")}
            {play_prompt("te", "menu_lang")}
            {play_prompt("mr", "menu_lang")}
            {play_prompt("ta", "menu_lang")}
            {play_prompt("gu", "menu_lang")}
            {play_prompt("kn", "menu_lang")}
            {play_prompt("ml", "menu_lang")}
        </Gather>

        {play_prompt("en", "invalid_selection")}
        <Redirect>/</Redirect>
    </Response>
    """
    return Response(twiml, mimetype="text/xml")


# ------------------------------------------------------
# 2) HANDLE LANGUAGE SELECTION
# ------------------------------------------------------
@app.route("/handle-language", methods=["POST"])
def handle_language():
    call_sid = request.form.get("CallSid", "")
    digit = (request.form.get("Digits") or "").strip()

    config = LANG_CONFIG.get(digit)
    if not config:
        twiml = f"""
        <Response>
            {play_prompt("en", "invalid_selection")}
            <Redirect>/</Redirect>
        </Response>
        """
        return Response(twiml, mimetype="text/xml")

    lang_key = config["lang_key"]

    # Save chosen language
    CALL_STATE[call_sid] = {
        "lang_key": lang_key,
        "attempts": 0,
        "name": None
    }

    # Ask name
    twiml = f"""
    <Response>
        <Gather input="speech dtmf" timeout="10" finishOnKey="*" action="/handle-name" method="POST">
            {play_prompt(lang_key, "ask_name")}
        </Gather>

        {play_prompt(lang_key, "did_not_receive_name_try_one_more_time")}
        <Redirect>/retry-name</Redirect>
    </Response>
    """
    return Response(twiml, mimetype="text/xml")


# ------------------------------------------------------
# 3) RETRY NAME
# ------------------------------------------------------
@app.route("/retry-name", methods=["POST"])
def retry_name():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    state["attempts"] = state.get("attempts", 0) + 1
    CALL_STATE[call_sid] = state

    lang_key = state.get("lang_key", "en")

    # Too many failures → skip name
    if state["attempts"] > 1:
        state["name"] = "Friend"
        CALL_STATE[call_sid] = state
        return ask_aadhaar_flow(state)

    # Ask name again
    twiml = f"""
    <Response>
        <Gather input="speech dtmf" timeout="10" finishOnKey="*" action="/handle-name" method="POST">
            {play_prompt(lang_key, "ask_name")}
        </Gather>

        {play_prompt(lang_key, "still_no_name_continue_without")}
        <Redirect>/skip-name</Redirect>
    </Response>
    """
    return Response(twiml, mimetype="text/xml")


# ------------------------------------------------------
# 4) SKIP NAME
# ------------------------------------------------------
@app.route("/skip-name", methods=["POST"])
def skip_name():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    state["name"] = "Friend"
    CALL_STATE[call_sid] = state
    return ask_aadhaar_flow(state)


# ------------------------------------------------------
# 5) HANDLE NAME
# ------------------------------------------------------
@app.route("/handle-name", methods=["POST"])
def handle_name():
    call_sid = request.form.get("CallSid", "")
    speech_text = (request.form.get("SpeechResult") or "").strip()
    dtmf = (request.form.get("Digits") or "").strip()

    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")

    if speech_text:
        name = speech_text
    elif dtmf:
        name = "Friend"
    else:
        # Could not hear → retry
        twiml = f"""
        <Response>
            {play_prompt(lang_key, "could_not_hear_name_try_again")}
            <Redirect>/retry-name</Redirect>
        </Response>
        """
        return Response(twiml, mimetype="text/xml")

    state["name"] = name
    CALL_STATE[call_sid] = state
    return ask_aadhaar_flow(state)


# ------------------------------------------------------
# Helper: Ask Aadhaar (shared)
# ------------------------------------------------------
def ask_aadhaar_flow(state):
    lang_key = state.get("lang_key", "en")

    twiml = f"""
    <Response>
        <Gather input="dtmf" numDigits="12" timeout="25" finishOnKey="#" action="/handle-aadhaar" method="POST">
            {play_prompt(lang_key, "ask_aadhaar")}
        </Gather>

        {play_prompt(lang_key, "did_not_receive_aadhar_try")}
        <Redirect>/retry-aadhaar</Redirect>
    </Response>
    """
    return Response(twiml, mimetype="text/xml")


# ------------------------------------------------------
# 6) RETRY AADHAAR
# ------------------------------------------------------
@app.route("/retry-aadhaar", methods=["POST"])
def retry_aadhaar():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")

    twiml = f"""
    <Response>
        <Gather input="dtmf" numDigits="12" timeout="25" finishOnKey="#" action="/handle-aadhaar" method="POST">
            {play_prompt(lang_key, "ask_aadhaar")}
        </Gather>

        {play_prompt(lang_key, "still_no_aadhar_goodbye")}
        <Hangup/>
    </Response>
    """
    return Response(twiml, mimetype="text/xml")


# ------------------------------------------------------
# 7) HANDLE AADHAAR INPUT
# ------------------------------------------------------
@app.route("/handle-aadhaar", methods=["POST"])
def handle_aadhaar():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")
    name = state.get("name", "Friend")

    digits = (request.form.get("Digits") or "").strip()

    if not digits or len(digits) < 6:
        twiml = f"""
        <Response>
            {play_prompt(lang_key, "aadhar_too_short")}
            <Redirect>/retry-aadhaar</Redirect>
        </Response>
        """
        return Response(twiml, mimetype="text/xml")

    # Lookup in mock DB
    db = load_mock_db()
    record = db.get(digits)

    if not record:
        twiml = f"""
        <Response>
            {play_prompt(lang_key, "sorry_not_found")}
            {play_prompt(lang_key, "ask_if_want_to_explain_source")}
            <Gather input="speech" timeout="6" finishOnKey="*" action="/handle-source" method="POST"/>
            {play_prompt(lang_key, "no_input_detected_goodbye")}
            <Hangup/>
        </Response>
        """
        return Response(twiml, mimetype="text/xml")

    # Record exists → begin summary generation
    state["aadhaar"] = digits
    state["record"] = record
    CALL_STATE[call_sid] = state

    if "stored_pdf" in record:
        pdf_path = BASE_DIR / record["stored_pdf"]

        if not pdf_path.exists():
            print("❌ stored_pdf not found:", pdf_path)
            notice_text = ""  
        else:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

            # Extract text using DocumentAI
            try:
                _, doc_text = call_document_ai(pdf_bytes)
                notice_text = doc_text
            except Exception as e:
                print("❌ DocumentAI failed:", e)
                notice_text = ""
    else:
        # Fallback to plain text
        notice_text = record.get("notice", "")


    # Trigger background summary
    requests.post(f"{request.url_root.rstrip('/')}/generate_explanation",
                  json={"text": notice_text, "language": lang_key, "quality": "high"},
                  timeout=3)

    # Ask user to wait
    twiml = f"""
    <Response>
        {play_prompt(lang_key, "please_wait_summary")}
        <Redirect>/wait-summary</Redirect>
    </Response>
    """
    return Response(twiml, mimetype="text/xml")


# ------------------------------------------------------
# 8) WAIT FOR SUMMARY (poll every 3s)
# ------------------------------------------------------
@app.route("/wait-summary", methods=["POST", "GET"])
def wait_summary():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")

    # poll summary endpoint
    poll = requests.post(f"{request.url_root.rstrip('/')}/poll-summary").json()

    if poll.get("ready"):
        if poll.get("has_audio"):
            audio_url = poll["audio_url"]
            # play audio summary
            twiml = f"""
            <Response>
                <Play>{audio_url}</Play>
                <Hangup/>
            </Response>
            """
        else:
            # read text summary fallback
            summary = poll.get("text", "")
            twiml = f"""
            <Response>
                {play_prompt(lang_key, "notice_not_readable")}
                <Say>{summary}</Say>
                <Hangup/>
            </Response>
            """

        # Clear state
        if call_sid in CALL_STATE:
            del CALL_STATE[call_sid]

        return Response(twiml, mimetype="text/xml")

    # Not ready → wait again
    twiml = f"""
    <Response>
        <Pause length="3"/>
        <Redirect>/wait-summary</Redirect>
    </Response>
    """
    return Response(twiml, mimetype="text/xml")


# ------------------------------------------------------
# 9) HANDLE SOURCE INPUT (fallback)
# ------------------------------------------------------
@app.route("/handle-source", methods=["POST"])
def handle_source():
    call_sid = request.form.get("CallSid", "")
    state = CALL_STATE.get(call_sid, {})
    lang_key = state.get("lang_key", "en")

    speech = (request.form.get("SpeechResult") or "").strip()

    if not speech:
        twiml = f"""
        <Response>
            {play_prompt(lang_key, "no_input_detected_goodbye")}
            <Hangup/>
        </Response>
        """
        return Response(twiml, mimetype="text/xml")

    # Save the provided info
    state["provided_source"] = speech
    CALL_STATE[call_sid] = state

    twiml = f"""
    <Response>
        {play_prompt(lang_key, "thanks_we_will_try_search_call_back")}
        <Hangup/>
    </Response>
    """
    return Response(twiml, mimetype="text/xml")
# ============================================
#  SERVER.PY — PART 4 OF 4
#  STATIC AUDIO + HEALTH + FINAL APP.RUN()
# ============================================

# ---------------------------------------------------
# Serve audio prompt files
# ---------------------------------------------------
@app.route("/audio/<path:filename>", methods=["GET"])
def serve_prompt_audio(filename):
    """
    Serves mp3 prompts located in /prompt_audio/
    Example: /audio/hi_ask_name.mp3
    """
    return send_from_directory(PROMPT_DIR, filename, mimetype="audio/mpeg")


# ---------------------------------------------------
# Serve generated summary audio (TTS)
# ---------------------------------------------------
@app.route("/summary-audio/<filename>", methods=["GET"])
def serve_summary_audio(filename):
    """
    Serves the generated TTS summary MP3.
    """
    return send_from_directory(BASE_DIR, filename, mimetype="audio/mpeg")


# ---------------------------------------------------
# Health check endpoint
# ---------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "twilio_ready": True, "flutter_ready": True}


# ---------------------------------------------------
# Reset summary state (Optional debug endpoint)
# ---------------------------------------------------
@app.post("/reset-summary")
def reset_summary():
    SUMMARY_STATE["ready"] = False
    SUMMARY_STATE["busy"] = False
    SUMMARY_STATE["audio_path"] = None
    SUMMARY_STATE["text"] = None
    return {"status": "reset"}


# ---------------------------------------------------
# Clean state on call completion (Twilio calls /status)
# ---------------------------------------------------
@app.route("/call-complete", methods=["POST"])
def call_complete_cleanup():
    """
    Optional: Configure Twilio call status callback → /call-complete
    to remove CALL_STATE gracefully.
    """
    call_sid = request.form.get("CallSid", "")
    if call_sid in CALL_STATE:
        del CALL_STATE[call_sid]
    return {"status": "cleaned"}


# ---------------------------------------------------
# START FLASK SERVER
# ---------------------------------------------------
if __name__ == "__main__":
    # IMPORTANT: Twilio requires externally accessible address → use ngrok
    # Example:
    #   ngrok http 5001
    #
    # Then set Twilio webhook:
    #   https://<ngrok-id>.ngrok.io
    #
    app.run(host="0.0.0.0", port=5000, debug=True)
