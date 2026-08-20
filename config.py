import os

DAILY_TARGET = int(os.getenv("DAILY_TARGET", "10"))
TIMEZONE = "America/Los_Angeles"

CHECKPOINTS = {
    17: ["kid", "parent"],
    21: ["kid", "parent"],
}

PADDING_MIN_QUESTIONS = 150
PADDING_MAX_MASTERED = 3

IXL_USER = os.getenv("IXL_USER")
IXL_PASS = os.getenv("IXL_PASS")
IXL_PROFILE = os.getenv("IXL_PROFILE")
IXL_PROFILE_PASS = os.getenv("IXL_PROFILE_PASS")

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM")
PHONE_KID = os.getenv("PHONE_KID")
PHONE_PARENT = os.getenv("PHONE_PARENT")

ENFORCEMENT_ENABLED = os.getenv("ENFORCEMENT_ENABLED", "false").lower() == "true"
NEXTDNS_API_KEY = os.getenv("NEXTDNS_API_KEY")
NEXTDNS_PROFILE = os.getenv("NEXTDNS_PROFILE")

RECON = os.getenv("RECON", "0") == "1"

MESSAGES = {
    15: "3pm check. You're at {done}/{target}. Knock it out before dinner.",
    17: "5pm. {done}/{target} done. Clock's running.",
    19: "7pm, still {done}/{target}. Two hours left.",
    21: "9pm. Final count: {done}/{target}. That's the day.",
}

PARENT_MESSAGES = {
    17: "IXL 5pm: he's at {done}/{target}.",
    21: "IXL final: {done}/{target}. Questions: {questions}. Minutes: {minutes}.",
}
