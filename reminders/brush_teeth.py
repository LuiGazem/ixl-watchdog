import os
import requests

TWILIO_SID = os.environ["TWILIO_SID"]
TWILIO_TOKEN = os.environ["TWILIO_TOKEN"]
TWILIO_FROM = os.environ["TWILIO_FROM"]
PHONE_KID = os.environ["PHONE_KID"]

def send_text(to, body):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
    resp = requests.post(
        url,
        data={"From": TWILIO_FROM, "To": to, "Body": body},
        auth=(TWILIO_SID, TWILIO_TOKEN),
        timeout=15,
    )
    resp.raise_for_status()
    print(f"sent to {to}: {resp.json().get('sid')}")

if __name__ == "__main__":
    send_text(PHONE_KID, "brush your teeth, send photo")
