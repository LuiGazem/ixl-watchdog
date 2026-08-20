#!/usr/bin/env python3
"""Weekly AI coach. Reads the state log, returns two messages."""
import json, pathlib, datetime, urllib.request

REPO = pathlib.Path.home() / "ixl-watchdog"
KEYF = pathlib.Path.home() / ".config" / "ixl_api_key"
MODEL = "claude-sonnet-5"
MIN_DAYS = 5


def key():
    try:
        return KEYF.read_text().strip()
    except Exception:
        return None


_P = json.loads((pathlib.Path.home() / ".config" / "ixl_people.json").read_text())
NAME = _P["name"]
BIRTHDAY = datetime.date(*[int(x) for x in _P["birthday"].split("-")])
GRADE_ANCHOR_YEAR = 2026   # school year starting Aug 2026
GRADE_AT_ANCHOR = 8        # he is in 8th grade that year


def school_year(today):
    """Returns (label, grade, next_grade). School year starts in August."""
    start = today.year if today.month >= 8 else today.year - 1
    grade = GRADE_AT_ANCHOR + (start - GRADE_ANCHOR_YEAR)
    return "{}-{}".format(start, start + 1), grade, grade + 1


def age(today):
    a = today.year - BIRTHDAY.year
    if (today.month, today.day) < (BIRTHDAY.month, BIRTHDAY.day):
        a -= 1
    return a


def gather(today, days=28):
    out = []
    for i in range(days):
        dt = today - datetime.timedelta(days=i)
        f = REPO / "state" / (dt.strftime("%Y-%m-%d") + ".json")
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        out.append({
            "date": dt.strftime("%a %Y-%m-%d"),
            "mastered": d.get("skills_mastered", 0),
            "questions": d.get("questions", 0),
            "minutes": d.get("minutes", 0),
            "skills": [{"name": s.get("name"), "min": s.get("minutes"),
                        "q": s.get("questions")}
                       for s in (d.get("skill_codes") or [])],
            "abandoned": [{"name": s.get("name"), "score": s.get("score"),
                           "min": s.get("minutes")}
                          for s in (d.get("in_progress") or [])],
            "regrind": [s.get("name") if isinstance(s, dict) else s
                        for s in (d.get("regrind_codes") or [])],
            "trouble": d.get("trouble_spots") or [],
        })
    out.reverse()
    return out


PROMPT = """You are {name}'s math teacher. Today is {today}. He is {age}. This is the {year} school year and he is in grade {grade}; next year he will be in grade {next_grade}. Use these, never guess his grade or age, and never say he is in a grade other than {grade}. His older brother set a goal of {target} mastered skills per day and sits with him when these messages arrive, so you are speaking to a supervised kid, not sending advice into the void.

You have his full practice log below, oldest first. This tracking only started recently, so days that are missing were NOT logged. Never claim he was inactive on a day that simply is not in the data.

Each day lists skills he drove to SmartScore 100 (mastered), skills he started and left unfinished (abandoned, with the score reached), skills already at 100 that he practiced again (regrind), and per-skill minutes and questions.

<data>
{data}
</data>

WHAT TO LOOK FOR

Read the numbers like a teacher who has seen a thousand kids. Minutes per question is your best tool.
- Judge pace in SECONDS PER QUESTION, and be careful here. Under 10 sec/question is genuinely suspicious. 10 to 25 sec/question is fast but plausible on multiple-choice or identify-the-setup skills. Over 25 sec/question is a normal working pace and is NOT evidence of guessing.
- Question COUNT matters as much as speed. IXL usually needs 20+ questions to reach SmartScore 100 from zero, and every wrong answer adds more. So a skill cleared in FEWER questions means he got nearly everything right first try. Few questions plus fast time means the skill was easy for him. Many questions plus fast time is the pattern that suggests guessing.
- Default to the generous reading. A fast clear usually means he found it easy, and telling a capable kid he cheated when he did not is worse than missing one instance of real guessing. Only raise guessing when the numbers are genuinely extreme, and say plainly that it might just mean the skill was easy.
- A skill that took far longer than his average means he was genuinely stuck, not lazy.
- Regrinding skills already at 100 is padding the clock.
- Abandoned skills that never get finished in later sessions are avoidance.
- Doing everything in one marathon then nothing for days is cramming, and it does not stick.
- Gaps in a lettered sequence, or a checkpoint passed in the same sitting as the skills it tests, mean the mastery is not real.
- Rising or falling effort across weeks matters more than any single day.

Say what the evidence supports and no more. If a number looks like guessing, say it looks like guessing and name the number. Do not accuse him of something the data does not show.

OUTPUT

Two sections, exactly these markers on their own lines, nothing before or after:

===KID===
(the message to {name})
===PARENT===
(the note to his brother)

THE MESSAGE TO {name}

Write as his teacher talking directly to him. Five to nine sentences. You may open with a blunt one-line verdict on the week.

Be firm. If the week was weak, say so plainly and say what specifically was not good enough. If you think he guessed through a skill, tell him you noticed and show him the number that gave it away. If he padded or skipped, call it. Do not soften it into nothing, and do not pile on either. You are demanding because you expect more from him, not because you are angry.

Be specific. Name actual skills from the data. Numbers make it real: minutes, questions, how a skill compares to his own pace elsewhere.

Explain consequences concretely. If he is shaky on something, say what it feeds into later, naming the grade or course it feeds into given that he is currently in grade {grade}, and what it will feel like to sit in that class without this. Make the future cost real rather than vague.

Give him one or two concrete instructions for the coming week. Redo a specific skill. Do not start a section until another one is solid. Break a marathon into shorter sessions.

When he genuinely earns praise, give it and mean it. Name what was good and why it was hard. If he did not earn it, do not manufacture it.

Plain direct language a 12-year-old reads without stopping. No exclamation marks, no emoji, no em dashes, no corporate encouragement, no "keep up the great work." Never insult him or call him lazy or stupid. Criticize the work and the pattern, never the kid.

THE NOTE TO HIS BROTHER

Up to 7 sentences. Lead with the most useful pattern you found. Say whether the daily target still looks right against his demonstrated pace. Flag suspected guessing, padding, avoidance, or a knowledge gap that will cause trouble later, and cite the numbers. Say plainly if the week was bad. Suggest one thing he could do sitting next to him this week. No em dashes.
"""


def build(today, target=10):
    days = gather(today)
    real = sum(1 for d in days if d["questions"] > 0)
    if real < MIN_DAYS:
        return None, "only {} days of data, need {}".format(real, MIN_DAYS)

    k = key()
    if not k:
        return None, "no API key at " + str(KEYF)

    body = json.dumps({
        "model": MODEL,
        "max_tokens": 8000,
        "messages": [{"role": "user", "content": PROMPT.format(
            target=target, data=json.dumps(days, separators=(",", ":")),
            today=today.strftime("%A %d %B %Y"), age=age(today),
            year=school_year(today)[0], grade=school_year(today)[1],
            next_grade=school_year(today)[2], name=NAME)}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": k,
                 "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            payload = json.loads(r.read())
        if payload.get("stop_reason") == "max_tokens":
            return None, "response truncated, raise max_tokens"
        text = "".join(b.get("text", "") for b in payload.get("content", [])
                       if b.get("type") == "text").strip()
        if "===KID===" not in text or "===PARENT===" not in text:
            return None, "markers missing: " + text[:200]
        kid = text.split("===KID===", 1)[1].split("===PARENT===", 1)[0].strip()
        parent = text.split("===PARENT===", 1)[1].strip()
        out = {"kid": kid, "parent": parent}
        if not out.get("kid") or not out.get("parent"):
            return None, "incomplete response"
        return out, None
    except Exception as e:
        return None, "api error: {}".format(e)


if __name__ == "__main__":
    o, err = build(datetime.date.today())
    print(err if err else json.dumps(o, indent=2))
