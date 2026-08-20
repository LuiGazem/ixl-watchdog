import requests
import config

API = "https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json"


def send(to, body):
    if not (config.TWILIO_SID and to):
        print("[dry-run] {}: {}".format(to, body))
        return False
    r = requests.post(
        API.format(config.TWILIO_SID),
        data={"From": config.TWILIO_FROM, "To": to, "Body": body},
        auth=(config.TWILIO_SID, config.TWILIO_TOKEN),
        timeout=20,
    )
    print("twilio", r.status_code, r.text[:200])
    return 200 <= r.status_code < 300


def to_kid(body):
    return send(config.PHONE_KID, body)


def to_parent(body):
    return send(config.PHONE_PARENT, body)
