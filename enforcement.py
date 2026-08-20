"""No-op today. Flip ENFORCEMENT_ENABLED=true later and this starts biting."""
import requests
import config

BLOCKED = ["youtube.com", "roblox.com", "tiktok.com", "discord.com", "twitch.tv"]


def sync(behind, hour):
    if not config.ENFORCEMENT_ENABLED:
        print("[enforcement off] behind={} hour={}".format(behind, hour))
        return
    if behind and hour >= 17:
        _set_blocklist(BLOCKED)
    else:
        _set_blocklist([])


def _set_blocklist(domains):
    url = "https://api.nextdns.io/profiles/{}/denylist".format(config.NEXTDNS_PROFILE)
    headers = {"X-Api-Key": config.NEXTDNS_API_KEY}
    existing = requests.get(url, headers=headers, timeout=20).json().get("data", [])
    for e in existing:
        requests.delete("{}/{}".format(url, e["id"]), headers=headers, timeout=20)
    for d in domains:
        requests.post(url, headers=headers, json={"id": d, "active": True}, timeout=20)
    print("[enforcement] blocklist set to", domains)
