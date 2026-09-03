import os
from twilio.rest import Client
from dotenv import load_dotenv

# Load credentials from your .env file
load_dotenv()

account_sid = os.getenv('TWILIO_ACCOUNT_SID')   
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_number = os.getenv('TWILIO_PHONE_NUMBER')
ngrok_url = os.getenv('SERVER_BASE_URL')

client = Client(account_sid, auth_token)

# The Indian number you want Twilio to call (must be your Verified Caller ID phone number)
YOUR_INDIAN_NUMBER = "+919954209026"  # <--- REPLACE THIS

print(f"Calling {YOUR_INDIAN_NUMBER} from {twilio_number}...")

try:
    call = client.calls.create(
        to=YOUR_INDIAN_NUMBER,
        from_=twilio_number,
        url=f"{ngrok_url}/"  # This connects the call directly to your VaaniPay app!
    )
    print("Call initiated! Your phone should ring in a few seconds.")
    print("Call SID:", call.sid)
except Exception as e:
    print("Error:", e)
