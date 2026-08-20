import json, pathlib, re, traceback
from playwright.sync_api import sync_playwright
import config

RECON_DIR = pathlib.Path("recon")
LOG = []

REPORT_URL = "https://www.ixl.com/analytics/progress-and-improvement"

EXTRACT_JS = """
() => {
  const rows = [...document.querySelectorAll('.skill-row')].map(r => {
    const nameEl = r.querySelector('.skill-name a span');
    const scores = [...r.querySelectorAll('.skill-improvement .score')]
      .map(s => parseInt(s.textContent.trim(), 10))
      .filter(n => !isNaN(n));
    return {
      name: nameEl ? nameEl.textContent.trim() : '',
      code: (r.querySelector('.permacode') || {}).textContent || '',
      time: (r.querySelector('.skill-time') || {}).textContent || '',
      questions: (r.querySelector('.skill-questions') || {}).textContent || '0',
      start: scores.length ? scores[0] : null,
      end: scores.length ? scores[scores.length - 1] : null
    };
  });
  const sel = document.querySelector('.date-range .option-selection');
  return { rows: rows, range: sel ? sel.textContent.trim() : '' };
}
"""


def note(msg):
    print("[scrape]", msg)
    LOG.append(str(msg))


def shot(page, name):
    if not config.RECON:
        return
    RECON_DIR.mkdir(exist_ok=True)
    try:
        page.screenshot(path=str(RECON_DIR / name), full_page=True)
        note("shot " + name)
    except Exception as e:
        note("shot failed " + name + " " + str(e))


def try_fill(page, selectors, value, label):
    for s in selectors:
        try:
            el = page.locator(s).first
            if el.count() > 0 and el.is_visible():
                el.fill(value)
                note("filled " + label)
                return True
        except Exception:
            continue
    note("COULD NOT FILL " + label)
    return False


def try_click(page, selectors, label):
    for s in selectors:
        try:
            el = page.locator(s).first
            if el.count() > 0 and el.is_visible():
                el.click()
                note("clicked " + label + " via " + s)
                return True
        except Exception:
            continue
    note("could not click " + label)
    return False


USER_SEL = ["input[name='username']", "input#qlusername", "input[type='text']"]
PASS_SEL = ["input[name='password']", "input#qlpassword", "input[type='password']"]
SUBMIT_SEL = ["button[type='submit']", "input[type='submit']", "button:has-text('Sign in')"]


def minutes_from(text):
    text = (text or "").lower()
    hrs = re.search(r"(\d+)\s*hr", text)
    mins = re.search(r"(\d+)\s*min", text)
    return (int(hrs.group(1)) * 60 if hrs else 0) + (int(mins.group(1)) if mins else 0)


def enter_secret_word(page, word):
    for s in ["xpath=//*[contains(text(),'secret word')]/following::input[1]",
              "input[type='password']:visible", "input:visible"]:
        try:
            loc = page.locator(s)
            if loc.count() == 0:
                continue
            el = loc.last if "visible" in s else loc.first
            if not el.is_visible():
                continue
            el.click()
            el.fill(word)
            el.press("Enter")
            page.wait_for_timeout(5000)
            note("secret word submitted")
            return True
        except Exception:
            continue
    note("NEVER FOUND SECRET WORD BOX")
    return False


def set_subject_math(page):
    try_click(page, [".subject-select .select-open", "*:has-text('SUBJECT:') >> .select-open"], "subject dropdown")
    page.wait_for_timeout(1200)
    ok = try_click(page, [
        ".select-body .option:text-is('Math')",
        ".option:has-text('Math')",
    ], "Math option")
    page.wait_for_timeout(5000)
    shot(page, "18_subject_math.png")
    return ok


TROUBLE_JS = """
() => {
  const spots = [...document.querySelectorAll('.trouble-spot')].map(el => {
    const nm = el.querySelector('.spot-name');
    if (!nm || nm.className.indexOf('no-data') !== -1) return null;
    const hr = el.querySelector('.header-right');
    const info = el.querySelector('.spot-info');
    return {
      name: nm.textContent.trim(),
      detail: hr ? hr.textContent.trim() : '',
      info: info ? info.textContent.trim().slice(0, 300) : ''
    };
  }).filter(Boolean);
  const sel = document.querySelector('.date-range .option-selection');
  return { spots: spots, range: sel ? sel.textContent.trim() : '' };
}
"""


def set_range(page, label):
    try_click(page, [".date-range .select-open", ".date-range .select-title"],
              "date dropdown")
    page.wait_for_timeout(1200)
    ok = try_click(page, [
        ".date-range .select-body .option:has-text('" + label + "')",
        ".date-range .option:has-text('" + label + "')",
    ], label)
    page.wait_for_timeout(6000)
    return ok


def fetch_trouble(page):
    try:
        page.goto("https://www.ixl.com/analytics/trouble-spots",
                  wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(4000)
        set_range(page, "Last 30 days")
        t = page.evaluate(TROUBLE_JS)
        note("trouble range " + repr(t.get("range")) +
             " spots " + str(len(t.get("spots", []))))
        return t.get("spots", [])
    except Exception as e:
        note("trouble fetch failed " + str(e))
        return []


def set_range_today(page):
    try_click(page, [".date-range .select-open", ".date-range .select-title"], "date range dropdown")
    page.wait_for_timeout(1200)
    shot(page, "20_range_open.png")
    clicked = try_click(page, [
        ".date-range .select-body .option:has-text('Today')",
        ".date-range .option:has-text('Today')",
    ], "Today option")
    page.wait_for_timeout(6000)
    shot(page, "21_range_today.png")
    return clicked


def wait_for_profile(page, profile, tries=6):
    """The picker can be slow. Poll for it instead of guessing a sleep."""
    for i in range(tries):
        for sel in ["text=" + profile, "img[alt*='" + profile + "']",
                    "[class*='profile']:has-text('" + profile + "')"]:
            try:
                el = page.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    el.click()
                    note("clicked profile on attempt " + str(i + 1))
                    return True
            except Exception:
                pass
        page.wait_for_timeout(2500)
    note("profile picker never appeared after " + str(tries) + " tries")
    return False


def fetch_today():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/128.0 Safari/537.36"),
            viewport={"width": 1440, "height": 1100},
        )
        page = ctx.new_page()

        try:
            page.goto("https://www.ixl.com/signin", wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2500)
            try_fill(page, USER_SEL, config.IXL_USER, "username")
            try_fill(page, PASS_SEL, config.IXL_PASS, "password")
            try_click(page, SUBMIT_SEL, "sign in")
            page.wait_for_timeout(6000)

            profile = config.IXL_PROFILE or ""
            if not profile:
                raise RuntimeError("IXL_PROFILE secret is not set")
            if wait_for_profile(page, profile):
                page.wait_for_timeout(3000)
                if config.IXL_PROFILE_PASS:
                    enter_secret_word(page, config.IXL_PROFILE_PASS)

            note("url after login: " + page.url)
            if "signin" in page.url:
                raise RuntimeError("login did not complete, still on signin")

            page.goto(REPORT_URL, wait_until="networkidle", timeout=45000)
            page.wait_for_timeout(5000)
            shot(page, "19_report_default.png")

            set_subject_math(page)
            set_range_today(page)

            if config.RECON:
                try:
                    page.goto("https://www.ixl.com/analytics/trouble-spots",
                              wait_until="networkidle", timeout=45000)
                    page.wait_for_timeout(6000)
                    RECON_DIR.mkdir(exist_ok=True)
                    (RECON_DIR / "trouble.html").write_text(page.content()[:900000])
                    shot(page, "30_trouble.png")
                    note("trouble spots captured, url " + page.url)
                except Exception as e:
                    note("trouble spots failed " + str(e))
                page.goto(REPORT_URL, wait_until="networkidle", timeout=45000)
                page.wait_for_timeout(4000)
                set_range_today(page)

            data = page.evaluate(EXTRACT_JS)
            note("date range reads: " + repr(data.get("range")))
            note("skill rows: " + str(len(data.get("rows", []))))

            if config.RECON:
                RECON_DIR.mkdir(exist_ok=True)
                (RECON_DIR / "captured.json").write_text(json.dumps(data, indent=2)[:900000])
                (RECON_DIR / "page.html").write_text(page.content()[:900000])
                (RECON_DIR / "log.txt").write_text("\n".join(LOG))
                browser.close()
                return {"recon": True}

            trouble = fetch_trouble(page)
            browser.close()

            if "today" not in (data.get("range") or "").lower():
                raise RuntimeError("date filter did not switch to Today, got " + repr(data.get("range")))

            out = summarize(data["rows"])
            out["trouble_spots"] = scrub(trouble)
            return out

        except Exception:
            note("FATAL")
            note(traceback.format_exc())
            shot(page, "99_crash.png")
            if config.RECON:
                RECON_DIR.mkdir(exist_ok=True)
                (RECON_DIR / "log.txt").write_text("\n".join(LOG))
                browser.close()
                return {"recon": True}
            browser.close()
            raise


def scrub(spots):
    """IXL markup embeds the student name. Strip it before anything is stored."""
    name = (config.IXL_PROFILE or "").strip()
    out = []
    for sp in spots:
        item = dict(sp)
        for k in ("name", "detail", "info"):
            v = item.get(k) or ""
            if name:
                v = v.replace(name + "'s", "the student's").replace(name, "the student")
            item[k] = v[:200]
        out.append(item)
    return out


def summarize(rows):
    mastered, codes, regrind, in_progress = 0, [], [], []
    questions, minutes = 0, 0
    for r in rows:
        code = (r.get("code") or "").strip()
        name = (r.get("name") or "").strip()
        start, end = r.get("start"), r.get("end")
        mins = minutes_from(r.get("time"))
        try:
            q = int(str(r.get("questions", "0")).strip() or 0)
        except ValueError:
            q = 0
        questions += q
        minutes += mins
        if end is None:
            continue
        item = {"code": code, "name": name, "minutes": mins, "questions": q}
        if end >= 100:
            if start is not None and start >= 100:
                regrind.append(item)
            else:
                mastered += 1
                codes.append(item)
        else:
            item["score"] = end
            in_progress.append(item)
    in_progress.sort(key=lambda x: -(x.get("score") or 0))
    return {
        "skills_mastered": mastered,
        "skill_codes": codes,
        "in_progress": in_progress,
        "skills_touched": len(rows),
        "regrind_codes": regrind,
        "questions": questions,
        "minutes": minutes,
    }
