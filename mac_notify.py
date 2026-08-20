#!/usr/bin/env python3
import json, subprocess, datetime, pathlib, sys, time
import coach

REPO   = pathlib.Path.home() / "ixl-watchdog"
_P = json.loads((pathlib.Path.home() / ".config" / "ixl_people.json").read_text())
KID     = _P["kid"]
PARENTS = _P["parents"]
PARENT  = PARENTS[0]
TARGET = 10
HOURS  = [17, 21, 23]
DIGEST_HOUR = 21
SENT   = pathlib.Path.home() / ".ixl_mac_sent.json"
GH     = "/opt/homebrew/bin/gh"

SCRIPT = '''on run argv
  set theTo to item 1 of argv
  set theBody to item 2 of argv
  tell application "Messages"
    set svc to 1st account whose service type = iMessage
    set bud to participant theTo of svc
    send theBody to bud
  end tell
end run'''


def imessage(to, body):
    r = subprocess.run(["osascript", "-e", SCRIPT, to, body],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("SEND FAILED", to, r.stderr.strip()[:200])
        return False
    print("sent", to, "|", body.replace("\n", " / ")[:150])
    return True


def imessage_parents(body):
    ok = True
    for n in PARENTS:
        ok = imessage(n, body) and ok
    return ok


# ---------- formatting ----------

def dur(mins):
    mins = int(mins or 0)
    if mins < 60:
        return "{} min".format(mins)
    return "{} hr {} min".format(mins // 60, mins % 60)


def trim(s, n):
    s = (s or "").strip()
    return s if len(s) <= n else s[:n - 3].rstrip() + "..."


def done_lines(d, width=200, limit=15):
    return ["- {} ({}m)".format(trim(s.get("name"), width), s.get("minutes", 0))
            for s in (d.get("skill_codes") or [])[:limit]]


def wip_lines(d, width=200, limit=5):
    return ["- {} ({}/100, {}m)".format(trim(s.get("name"), width),
                                        s.get("score"), s.get("minutes", 0))
            for s in (d.get("in_progress") or [])[:limit]]


# ---------- messages ----------

def kid_behind(hour, d):
    done = d.get("skills_mastered", 0)
    lead = {17: "5pm check.", 21: "9pm check.",
            23: "Last call before midnight."}.get(hour, "Check.")
    L = ["{} {}/{} done.".format(lead, done, TARGET)]
    dl = done_lines(d)
    if dl:
        L += ["", "Finished:"] + dl
    wl = wip_lines(d)
    if wl:
        L += ["", "Working on:"] + wl
    tail = ("{} to go. {} so far." if hour != 23
            else "Day is over at {} short. {} total.")
    L += ["", tail.format(TARGET - done, dur(d.get("minutes")))]
    return "\n".join(L)


def parent_behind(hour, d):
    done = d.get("skills_mastered", 0)
    lead = {17: "IXL 5pm", 21: "IXL 9pm",
            23: "IXL end of day"}.get(hour, "IXL")
    L = ["{}: {}/{}. {} questions, {}.".format(
        lead, done, TARGET, d.get("questions", 0), dur(d.get("minutes")))]
    dl = done_lines(d)
    if dl:
        L += ["", "Finished:"] + dl
    wl = wip_lines(d)
    if wl:
        L += ["", "In progress:"] + wl
    rg = d.get("regrind_codes") or []
    if rg:
        names = [trim(r.get("name") if isinstance(r, dict) else str(r), 200)
                 for r in rg[:3]]
        L += ["", "Re-grinding: " + ", ".join(names)]
    return "\n".join(L)


def over_note(d):
    n = d.get("skills_mastered", 0) - TARGET
    return "" if n <= 0 else " That is {} over the goal.".format(n)


def kid_over(hour, d):
    done = d.get("skills_mastered", 0)
    lead = {21: "9pm check.", 23: "End of day."}.get(hour, "Check.")
    L = ["{} {}/{}.{}".format(lead, done, TARGET, over_note(d)), ""]
    L += done_lines(d)
    L += ["", "Total: {}, {} questions.".format(
        dur(d.get("minutes")), d.get("questions", 0))]
    return "\n".join(L)


def parent_over(hour, d):
    done = d.get("skills_mastered", 0)
    lead = {21: "IXL 9pm", 23: "IXL end of day"}.get(hour, "IXL")
    L = ["{}: {}/{}.{} {} questions, {}.".format(
        lead, done, TARGET, over_note(d),
        d.get("questions", 0), dur(d.get("minutes"))), ""]
    L += done_lines(d)
    wl = wip_lines(d)
    if wl:
        L += ["", "In progress:"] + wl
    return "\n".join(L)


def kid_done(d):
    L = ["{}/{}. Done for the day.{}".format(
        d.get("skills_mastered", 0), TARGET, over_note(d)), ""]
    L += done_lines(d)
    L += ["", "Total: {}, {} questions.".format(
        dur(d.get("minutes")), d.get("questions", 0)), "Good work."]
    return "\n".join(L)


def parent_done(d):
    L = ["IXL: he finished {}/{}.{}".format(
        d.get("skills_mastered", 0), TARGET, over_note(d)), ""]
    L += done_lines(d)
    L += ["", "Total: {}, {} questions.".format(
        dur(d.get("minutes")), d.get("questions", 0))]
    return "\n".join(L)


# ---------- weekly digest ----------

def week_stats(end, days=7):
    s = q = m = 0
    hits = 0
    per_day = []
    for i in range(days):
        dt = end - datetime.timedelta(days=i)
        f = REPO / "state" / (dt.strftime("%Y-%m-%d") + ".json")
        if f.exists():
            x = json.loads(f.read_text())
            ds, dq, dm = (x.get("skills_mastered", 0), x.get("questions", 0),
                          x.get("minutes", 0))
        else:
            ds = dq = dm = 0
        s += ds; q += dq; m += dm
        if ds >= TARGET:
            hits += 1
        per_day.append((dt, ds))
    per_day.reverse()
    return {"skills": s, "questions": q, "minutes": m, "hits": hits,
            "days": days, "per_day": per_day}


def digest(today):
    a = week_stats(today)
    b = week_stats(today - datetime.timedelta(days=7))
    start = (today - datetime.timedelta(days=6)).strftime("%b %-d")
    avg_a = a["skills"] / 7.0
    avg_b = b["skills"] / 7.0

    L = ["IXL week: {} - {}".format(start, today.strftime("%b %-d")), ""]
    L.append("{} skills, {} questions, {}".format(
        a["skills"], a["questions"], dur(a["minutes"])))
    L.append("Daily avg: {:.1f} skills".format(avg_a))
    L.append("Hit {}: {} of 7 days".format(TARGET, a["hits"]))
    if a["skills"]:
        L.append("Avg time per skill: {} min".format(
            round(a["minutes"] / max(a["skills"], 1))))

    best = max(a["per_day"], key=lambda x: x[1])
    worst = min(a["per_day"], key=lambda x: x[1])
    L.append("Best: {} ({}), worst: {} ({})".format(
        best[0].strftime("%a"), best[1], worst[0].strftime("%a"), worst[1]))

    L += ["", "Daily: " + " ".join(str(n) for _, n in a["per_day"])]

    spots = []
    for i in range(7):
        dt = today - datetime.timedelta(days=i)
        f = REPO / "state" / (dt.strftime("%Y-%m-%d") + ".json")
        if f.exists():
            spots = json.loads(f.read_text()).get("trouble_spots") or []
            if spots:
                break
    if spots:
        L += ["", "Trouble spots (30d):"]
        for sp in spots[:5]:
            line = "- " + sp.get("name", "")
            if sp.get("detail"):
                line += " (" + sp["detail"] + ")"
            L.append(line)

    if b["skills"]:
        delta = avg_a - avg_b
        word = "up" if delta > 0.3 else ("down" if delta < -0.3 else "flat")
        L.append("Last week avg {:.1f}. Trending {}.".format(avg_b, word))
    return "\n".join(L)


# ---------- plumbing ----------

def refresh():
    try:
        r = subprocess.run([GH, "workflow", "run", "ixl-watchdog"],
                           cwd=str(REPO), capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            print("trigger failed:", r.stderr.strip()[:200])
            return False
        print("scrape triggered")
        time.sleep(20)
        for _ in range(14):
            q = subprocess.run(
                [GH, "run", "list", "--workflow", "ixl-watchdog", "--limit", "1",
                 "--json", "status,conclusion",
                 "-q", ".[0].status + \"/\" + (.[0].conclusion // \"\")"],
                cwd=str(REPO), capture_output=True, text=True, timeout=60)
            if q.stdout.strip() == "completed":
                print("scrape done")
                return True
            time.sleep(15)
        print("scrape timed out")
    except Exception as e:
        print("refresh error:", e)
    return False


def load_sent(today):
    if SENT.exists():
        x = json.loads(SENT.read_text())
        if x.get("date") == today:
            return x
    return {"date": today, "sent": [], "flags": []}


def main():
    test = "--test" in sys.argv
    digest_only = "--digest" in sys.argv
    now = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")

    # Only burn Actions minutes when a message could actually fire.
    need_fresh = (now.hour in HOURS or now.hour == DIGEST_HOUR
                  or "--test" in sys.argv or "--digest" in sys.argv)
    ok_refresh = refresh() if need_fresh else True
    if not need_fresh:
        print("off-checkpoint run, reading last committed data")
    subprocess.run(["git", "-C", str(REPO), "pull", "-q"], capture_output=True)

    st = load_sent(today)

    def flag(key, msg):
        if key in st["flags"]:
            return
        imessage_parents("IXL watchdog problem: " + msg)
        st["flags"].append(key)

    if digest_only:
        imessage_parents(digest(now.date()))
        return

    f = REPO / "state" / (today + ".json")
    if not f.exists():
        print("no state file")
        if now.hour >= 17:
            flag("nofile", "no data file for today. The scraper may be down.")
        SENT.write_text(json.dumps(st, indent=2))
        return

    d = json.loads(f.read_text())
    done = d.get("skills_mastered", 0)

    h = REPO / "state" / "_health.json"
    if h.exists() and json.loads(h.read_text()).get("fails", 0) >= 2:
        flag("fails", "the IXL scrape has failed twice in a row. Numbers are not trustworthy.")

    if (now.hour >= 21 and done == 0
            and d.get("questions", 0) == 0 and d.get("minutes", 0) == 0):
        flag("allzero", "today reads 0 skills, 0 questions, 0 minutes. That usually means a broken parser, not a lazy day.")

    if not ok_refresh:
        flag("stale", "could not trigger a fresh scrape. Numbers may be stale.")

    if test:
        imessage(KID, kid_behind(17, d))
        imessage_parents(parent_behind(17, d))
        imessage_parents(digest(now.date()))
        return

    stale_guard = (not ok_refresh) and done < TARGET
    if stale_guard:
        print("refresh failed and he is behind, not sending on stale data")
        SENT.write_text(json.dumps(st, indent=2))
        return

    if done >= TARGET:
        if "done" not in st["sent"]:
            a = imessage(KID, kid_done(d))
            b = imessage_parents(parent_done(d))
            if a and b:
                st["sent"].append("done")
                st["done_at"] = done
        else:
            for hour in [21, 23]:
                if (now.hour >= hour and hour not in st["sent"]
                        and done > st.get("done_at", TARGET)):
                    a = imessage(KID, kid_over(hour, d))
                    b = imessage_parents(parent_over(hour, d))
                    if a and b:
                        st["sent"].append(hour)
                        st["done_at"] = done
    else:
        for hour in HOURS:
            if now.hour >= hour and hour not in st["sent"]:
                a = imessage(KID, kid_behind(hour, d))
                b = imessage_parents(parent_behind(hour, d))
                if a and b:
                    st["sent"].append(hour)

    if (now.weekday() == 6 and now.hour >= DIGEST_HOUR
            and "digest" not in st["sent"]):
        if imessage_parents(digest(now.date())):
            st["sent"].append("digest")
        c, err = coach.build(now.date(), TARGET)
        if c:
            imessage(KID, c["kid"])
            imessage_parents("Coach note:\n\n" + c["parent"])
        else:
            print("coach skipped:", err)

    SENT.write_text(json.dumps(st, indent=2))
    print(today, now.hour, "->", done, "/", TARGET, st["sent"])


if __name__ == "__main__":
    main()
