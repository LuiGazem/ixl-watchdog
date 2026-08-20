import json, pathlib, datetime, traceback
from zoneinfo import ZoneInfo
import config, scrape, alerts, enforcement

STATE = pathlib.Path("state")
STATE.mkdir(exist_ok=True)


def load(name, default):
    f = STATE / name
    return json.loads(f.read_text()) if f.exists() else default


def save(name, data):
    (STATE / name).write_text(json.dumps(data, indent=2))


def main():
    now = datetime.datetime.now(ZoneInfo(config.TIMEZONE))
    today = now.strftime("%Y-%m-%d")
    hour = now.hour

    health = load("_health.json", {"fails": 0})

    try:
        data = scrape.fetch_today()
        if data.get("recon"):
            print("recon complete, check artifacts")
            return
        health["fails"] = 0
    except Exception:
        traceback.print_exc()
        health["fails"] += 1
        save("_health.json", health)
        if health["fails"] >= 2:
            alerts.to_parent("IXL watchdog is broken. Scrape failed twice. "
                             "Today's numbers are NOT trustworthy.")
        return

    day = load(today + ".json", {"date": today, "sent": [], "padding_flagged": False})
    day.update(data)
    day["scraped_at"] = now.isoformat()
    done = data["skills_mastered"]
    behind = done < config.DAILY_TARGET

    if (not day["padding_flagged"]
            and data["questions"] >= config.PADDING_MIN_QUESTIONS
            and done <= config.PADDING_MAX_MASTERED):
        alerts.to_parent("Padding flag: {} questions but only {} skills mastered. "
                         "He's grinding easy stuff.".format(data["questions"], done))
        day["padding_flagged"] = True

    for cp_hour, who in sorted(config.CHECKPOINTS.items()):
        if hour >= cp_hour and cp_hour not in day["sent"] and behind:
            ok = True
            if "kid" in who:
                ok = alerts.to_kid(config.MESSAGES[cp_hour].format(
                    done=done, target=config.DAILY_TARGET)) and ok
            if "parent" in who and cp_hour in config.PARENT_MESSAGES:
                ok = alerts.to_parent(config.PARENT_MESSAGES[cp_hour].format(
                    done=done, target=config.DAILY_TARGET,
                    questions=data["questions"], minutes=data["minutes"])) and ok
            if ok:
                day["sent"].append(cp_hour)
            else:
                print("send failed for checkpoint", cp_hour, "will retry next run")

    enforcement.sync(behind, hour)

    save(today + ".json", day)
    save("_health.json", health)
    print("{} {}:00 -> {}/{}".format(today, hour, done, config.DAILY_TARGET))


if __name__ == "__main__":
    main()
