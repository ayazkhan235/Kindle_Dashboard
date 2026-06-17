#!/usr/bin/env python3
import os, subprocess, json, re
from datetime import datetime, timedelta
from pathlib import Path
import requests
import feedparser
from readability import Document
import config

BASE_DIR = Path(__file__).parent

KINDLE_SSH = ["ssh", "-p", "2222", "-o", "ConnectTimeout=5",
              "-o", "StrictHostKeyChecking=no", "root@172.20.10.2"]

CSS = """
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
html, body { margin: 0; padding: 0; }
body { font-family: Georgia, serif; font-size: 21px; background: #fff; color: #000; }
.screen { height: 100vh; display: flex; flex-direction: column; }
.tab-content { flex: 1; overflow-y: auto; padding: 22px 24px 28px; display: none; }
.tab-content.active { display: block; }

nav { display: flex; background: #000; height: 70px; flex-shrink: 0; }
nav button { flex: 1; background: none; border: none; border-right: 1px solid #444; color: #999; font-size: 13px; font-family: Georgia, serif; cursor: pointer; padding: 0; letter-spacing: 0.5px; }
nav button:last-child { border-right: none; }
nav button.active { background: #fff; color: #000; font-weight: bold; }

h2 { font-size: 13px; font-weight: bold; border-bottom: 3px double #000; padding-bottom: 6px; margin: 30px 0 14px; text-transform: uppercase; letter-spacing: 3px; }
h2:first-child { margin-top: 0; }

.meta { font-size: 13px; color: #999; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 20px; border-bottom: 1px solid #000; padding-bottom: 10px; }

.temp { font-size: 96px; font-weight: bold; line-height: 0.95; letter-spacing: -3px; }
.cond { font-size: 26px; font-style: italic; margin: 4px 0 18px; color: #222; }
.wmeta { font-size: 18px; color: #333; margin: 8px 0; line-height: 1.4; }
.rain-row { margin: 16px 0 0; font-size: 15px; color: #555; line-height: 1.9; }

.news-item { border-bottom: 1px solid #ccc; padding: 18px 0; cursor: pointer; }
.news-item:first-child { padding-top: 4px; }
.news-title { font-size: 22px; font-weight: bold; line-height: 1.3; color: #000; }
.news-src { font-size: 13px; color: #999; margin-top: 6px; text-transform: uppercase; letter-spacing: 1px; }
.news-list.hidden { display: none; }
.article-view { display: none; }
.article-view.active { display: block; }
.back-btn { font-size: 15px; color: #fff; background: #000; border: none; padding: 11px 22px; display: inline-block; margin-bottom: 20px; cursor: pointer; font-family: Georgia, serif; letter-spacing: 1px; }
.article-src { font-size: 13px; color: #999; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px; }
.article-title { font-size: 28px; font-weight: bold; line-height: 1.25; margin-bottom: 20px; }
.article-body { font-size: 20px; line-height: 1.75; }
.article-body p { margin: 0 0 18px; }

.event { padding: 14px 0; border-bottom: 1px solid #ddd; }
.event-title { font-size: 21px; font-weight: bold; }
.event-time { font-size: 15px; color: #777; margin-top: 4px; }
.task { padding: 13px 0; border-bottom: 1px solid #ddd; font-size: 20px; }

.stat-row { margin-bottom: 22px; }
.stat-label { font-size: 12px; color: #999; text-transform: uppercase; letter-spacing: 2px; display: block; margin-bottom: 4px; }
.stat-val { font-size: 44px; font-weight: bold; line-height: 1; }
.log-text { font-size: 15px; color: #555; margin-top: 6px; word-break: break-word; line-height: 1.5; }
.rate-row { font-size: 22px; margin-bottom: 12px; }

.book-item { border-bottom: 1px solid #ddd; padding: 18px 0; }
.book-title { font-size: 21px; font-weight: bold; line-height: 1.3; }
.book-meta { font-size: 14px; color: #777; margin-top: 8px; display: flex; align-items: center; gap: 12px; }
.progress-wrap { flex: 1; height: 6px; background: #ddd; overflow: hidden; }
.progress-fill { height: 100%; background: #000; }
.format-badge { font-size: 11px; border: 1px solid #999; padding: 2px 7px; color: #777; flex-shrink: 0; letter-spacing: 1px; }
.empty { color: #aaa; font-style: italic; padding: 20px 0; font-size: 18px; }
.exit-btn { width: 100%; padding: 20px; font-size: 21px; font-family: Georgia, serif; background: #000; color: #fff; border: none; cursor: pointer; margin-bottom: 24px; letter-spacing: 1px; }

#exit-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: #fff; z-index: 100; align-items: center; justify-content: center; }
#exit-overlay div { font-size: 26px; font-style: italic; text-align: center; line-height: 1.5; }
"""


def fetch_weather():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": config.MUMBAI_LAT,
        "longitude": config.MUMBAI_LON,
        "current": "temperature_2m,apparent_temperature,weathercode,precipitation,windspeed_10m,relativehumidity_2m,uv_index",
        "hourly": "precipitation_probability",
        "daily": "sunrise,sunset",
        "timezone": "Asia/Kolkata",
        "forecast_days": 1,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        d = r.json()
        current = d["current"]
        hourly = d["hourly"]
        daily = d["daily"]
        now_hour = datetime.now().hour
        rain_hours = hourly["precipitation_probability"][now_hour:now_hour+8]
        rain_times = hourly["time"][now_hour:now_hour+8]
        max_rain = max(rain_hours) if rain_hours else 0
        wcode = current["weathercode"]
        uv = round(current.get("uv_index", 0))
        return {
            "temp": round(current["temperature_2m"]),
            "feels": round(current["apparent_temperature"]),
            "condition": weather_code_label(wcode),
            "wind": round(current["windspeed_10m"]),
            "humidity": current.get("relativehumidity_2m", "--"),
            "rain_chance": max_rain,
            "rain_hours": list(zip(rain_times, rain_hours)),
            "precip": current["precipitation"],
            "uv": uv,
            "uv_label": uv_label(uv),
            "sunrise": daily["sunrise"][0].split("T")[1] if daily.get("sunrise") else "--",
            "sunset": daily["sunset"][0].split("T")[1] if daily.get("sunset") else "--",
        }
    except Exception as e:
        return {"temp": "--", "feels": "--", "condition": "unavailable", "wind": "--",
                "humidity": "--", "rain_chance": 0, "rain_hours": [], "precip": 0,
                "uv": "--", "uv_label": "--", "sunrise": "--", "sunset": "--"}


def uv_label(uv):
    if isinstance(uv, str): return ""
    if uv <= 2: return "Low"
    if uv <= 5: return "Moderate"
    if uv <= 7: return "High"
    if uv <= 10: return "Very High"
    return "Extreme"


def weather_code_label(code):
    labels = {
        0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Foggy", 51: "Light drizzle", 53: "Drizzle",
        55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
        71: "Light snow", 73: "Snow", 80: "Showers", 81: "Showers",
        82: "Heavy showers", 95: "Thunderstorm", 99: "Thunderstorm",
    }
    return labels.get(code, f"Code {code}")


def fetch_aqi():
    try:
        url = f"https://api.waqi.info/feed/mumbai/?token={config.WAQI_TOKEN}"
        r = requests.get(url, timeout=10)
        d = r.json()
        if d["status"] == "ok":
            aqi = d["data"]["aqi"]
            return {"aqi": aqi, "label": aqi_label(aqi)}
    except:
        pass
    return {"aqi": "--", "label": ""}


def aqi_label(aqi):
    if aqi <= 50: return "Good"
    if aqi <= 100: return "Moderate"
    if aqi <= 150: return "Sensitive"
    if aqi <= 200: return "Unhealthy"
    if aqi <= 300: return "Very Unhealthy"
    return "Hazardous"


def fetch_currency():
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        d = r.json()
        rates = d.get("rates", {})
        usd_inr = round(rates.get("INR", 0), 2)
        eur_usd = rates.get("EUR", 1)
        eur_inr = round(usd_inr / eur_usd, 2) if eur_usd else "--"
        return {"usd_inr": usd_inr, "eur_inr": eur_inr}
    except:
        return {"usd_inr": "--", "eur_inr": "--"}


def fetch_calendar():
    try:
        result = subprocess.run(
            ["icalBuddy", "-n", "-nrd", "-b", "• ", "-iep", "title,datetime",
             "-po", "title,datetime", "eventsToday"],
            capture_output=True, text=True, timeout=15
        )
        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        events = []
        current = {}
        for line in lines:
            if line.startswith("•"):
                if current:
                    events.append(current)
                current = {"title": line[1:].strip(), "time": ""}
            elif current:
                current["time"] = line
        if current:
            events.append(current)
        return events[:8]
    except:
        return []


def fetch_reminders():
    try:
        result = subprocess.run(
            ["reminders", "show", "all"],
            capture_output=True, text=True, timeout=10
        )
        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        return [l.lstrip("•-* ") for l in lines if l][:10]
    except:
        return []


def fetch_outreach_db():
    try:
        import sqlite3
        conn = sqlite3.connect(config.OUTREACH_DB)
        c = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")

        c.execute("SELECT COUNT(*) FROM leads WHERE date(first_sent_at)=?", (today,))
        today_sent = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM leads WHERE status IN ('SENT','FOLLOW_UP_1','CONTACT_UPGRADED')")
        in_pipeline = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM leads WHERE status NOT IN ('NEW','NOT_FOUND','WRONG_CONTACT')")
        total_sent = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM leads WHERE reply_type IS NOT NULL AND reply_type != ''")
        replied = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM leads WHERE status='NEW'")
        pending = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM leads WHERE status='BOUNCED'")
        bounced = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM opens")
        opens = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM leads WHERE date(next_followup_at)=?", (today,))
        followups_due = c.fetchone()[0]

        open_rate = round(opens / max(total_sent, 1) * 100)
        reply_rate = round(replied / max(total_sent, 1) * 100)

        c.execute("""SELECT e.created_at, e.event_type, l.company
                     FROM events e JOIN leads l ON e.email=l.email
                     ORDER BY e.created_at DESC LIMIT 5""")
        events = [{"date": (r[0] or "")[:10], "type": r[1], "company": r[2] or ""}
                  for r in c.fetchall()]
        conn.close()
        return {"today_sent": today_sent, "in_pipeline": in_pipeline,
                "total_sent": total_sent, "replied": replied, "pending": pending,
                "bounced": bounced, "opens": opens, "followups_due": followups_due,
                "open_rate": open_rate, "reply_rate": reply_rate, "events": events}
    except Exception as e:
        return {"today_sent": "--", "in_pipeline": "--", "total_sent": "--",
                "replied": "--", "pending": "--", "bounced": "--", "opens": "--",
                "followups_due": 0, "open_rate": "--", "reply_rate": "--", "events": []}


def fetch_hn_top(n=5):
    try:
        ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json",
                           timeout=8).json()[:n]
        stories = []
        for sid in ids:
            try:
                s = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                                 timeout=5).json()
                stories.append({"title": s.get("title", ""), "score": s.get("score", 0),
                                 "by": s.get("by", "")})
            except Exception:
                pass
        return stories
    except Exception:
        return []


def fetch_github():
    try:
        token = config.GITHUB_TOKEN
        if not token:
            return {"repos": [], "pr_count": "--", "issue_count": "--", "username": ""}
        headers = {"Authorization": f"token {token}",
                   "Accept": "application/vnd.github.v3+json"}
        user = requests.get("https://api.github.com/user", headers=headers, timeout=8).json()
        username = user.get("login", config.GITHUB_USERNAME)
        repos_raw = requests.get(
            "https://api.github.com/user/repos?sort=pushed&per_page=6&type=owner",
            headers=headers, timeout=8).json()
        repos = [{"name": r["name"],
                  "pushed": r["pushed_at"][:10] if r.get("pushed_at") else "",
                  "private": r.get("private", False)}
                 for r in repos_raw if isinstance(r, dict)][:6]
        prs = requests.get(
            f"https://api.github.com/search/issues?q=is:pr+is:open+author:{username}",
            headers=headers, timeout=8).json()
        pr_count = prs.get("total_count", 0)
        issues_raw = requests.get(
            "https://api.github.com/issues?state=open&per_page=10",
            headers=headers, timeout=8).json()
        issue_count = len(issues_raw) if isinstance(issues_raw, list) else 0
        return {"repos": repos, "pr_count": pr_count,
                "issue_count": issue_count, "username": username}
    except Exception:
        return {"repos": [], "pr_count": "--", "issue_count": "--", "username": ""}


def fetch_notes(n=3):
    try:
        script = '''tell application "Notes"
    set out to {}
    repeat with i from 1 to ''' + str(n) + '''
        try
            set nt to note i of default account
            set bd to plaintext of nt
            if length of bd > 200 then set bd to text 1 thru 200 of bd
            set out to out & {name of nt & "|||" & bd}
        end try
    end repeat
    return out
end tell'''
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return []
        notes = []
        for item in result.stdout.strip().split(", "):
            if "|||" in item:
                title, preview = item.split("|||", 1)
                notes.append({"title": title.strip(), "preview": preview.strip()})
        return notes
    except Exception:
        return []


def fetch_outreach_status():
    try:
        log_path = config.OUTREACH_LOG
        if not os.path.exists(log_path):
            candidates = list(Path("/Users/ayazkhan/outreach_bot").rglob("*.log"))
            if candidates:
                log_path = str(candidates[0])
            else:
                return {"emails_today": "--", "last_action": "log not found"}
        result = subprocess.run(["tail", "-50", log_path], capture_output=True, text=True)
        lines = result.stdout.splitlines()
        today = datetime.now().strftime("%Y-%m-%d")
        today_lines = [l for l in lines if today in l]
        sent = sum(1 for l in today_lines if "sent" in l.lower() or "email" in l.lower())
        last = today_lines[-1] if today_lines else (lines[-1] if lines else "no entries")
        return {"emails_today": sent, "last_action": last[-100:]}
    except Exception as e:
        return {"emails_today": "--", "last_action": str(e)[:80]}


def fetch_news():
    articles = []
    for feed_url in config.RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                articles.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "source": feed.feed.get("title", ""),
                    "summary": entry.get("summary", "")[:300],
                })
                if len(articles) >= config.MAX_ARTICLES:
                    break
        except:
            pass
        if len(articles) >= config.MAX_ARTICLES:
            break
    return articles[:config.MAX_ARTICLES]


def fetch_article_body(url):
    try:
        from html import unescape
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        html = r.text
        # BBC: paragraphs carry a Paragraph-styles class
        paras = re.findall(r'<p class="Paragraph-styles[^"]*">(.*?)</p>', html, re.S)
        clean = [unescape(re.sub(r'<[^>]+>', '', p)).strip() for p in paras]
        clean = [c for c in clean if c]
        if len(clean) >= 3:
            return "".join(f"<p>{c}</p>" for c in clean)
        doc = Document(html)
        return doc.summary()
    except Exception:
        return None


def fetch_books():
    try:
        cmd = (
            'cd /mnt/us/koreader/books 2>/dev/null || exit 0; '
            'for f in *.epub *.mobi *.azw *.azw3 *.pdf; do '
            '[ -f "$f" ] || continue; '
            'ext="${f##*.}"; base="${f%.*}"; '
            'sdr="$base.sdr/metadata.$ext.lua"; progress=""; '
            '[ -f "$sdr" ] && progress=$(grep percent_finished "$sdr" | grep -oE "[0-9.]+" | tail -1); '
            'echo "$f|$progress"; done'
        )
        result = subprocess.run(KINDLE_SSH + [cmd], capture_output=True, text=True, timeout=15)
        books = []
        for line in result.stdout.strip().split('\n'):
            if not line.strip() or '|' not in line:
                continue
            filename, progress_str = line.strip().split('|', 1)
            ext = filename.rsplit('.', 1)[-1].upper() if '.' in filename else ''
            name = filename.rsplit('.', 1)[0]
            name = re.sub(r'\s*-?\s*libgen\.li$', '', name, flags=re.I)
            name = re.sub(r'\s*\(\d{4},[^)]*\)', '', name)        # drop (year, publisher)
            name = re.sub(r'\{\d{6,}\}', '', name)                # drop libgen id {123456}
            name = re.sub(r'^\[[^\]]*\]\s*', '', name)            # drop leading [series]
            m = re.match(r'^[^,]+,?\s+[A-Z]\w*\s*-\s*(.+)', name)  # "Author - Title"
            if ' - ' in name:
                name = name.split(' - ', 1)[1]
            name = re.sub(r'\{[^}]*\}', ' ', name)                # drop {author} braces
            name = re.sub(r'_', ' ', name)
            name = re.sub(r'\s+', ' ', name).strip(' .')
            progress = None
            if progress_str.strip():
                try:
                    progress = round(float(progress_str.strip()) * 100)
                except Exception:
                    pass
            books.append({'title': name, 'filename': filename, 'format': ext, 'progress': progress})
        books.sort(key=lambda b: (b['progress'] is None, -(b['progress'] or 0)))
        return books
    except Exception:
        return []


def claude_reset_countdown():
    today = datetime.now()
    day = config.CLAUDE_BILLING_DAY
    next_reset = today.replace(day=day, hour=0, minute=0, second=0, microsecond=0)
    if next_reset <= today:
        if today.month == 12:
            next_reset = next_reset.replace(year=today.year + 1, month=1)
        else:
            next_reset = next_reset.replace(month=today.month + 1)
    delta = next_reset - today
    return f"{delta.days}d {delta.seconds // 3600}h"


def build_html(weather, aqi, currency, articles, events, reminders, outreach, claude_reset, article_bodies, books):
    updated = datetime.now().strftime("%d %b %Y, %I:%M %p")

    # --- HOME TAB ---
    rain_parts = []
    for t, pct in weather["rain_hours"]:
        hour = t.split("T")[1][:5] if "T" in t else t
        rain_parts.append(f"{hour}&nbsp;{pct}%")
    rain_line = " &nbsp;|&nbsp; ".join(rain_parts)

    home_html = f"""<div class="meta">Updated {updated}</div>
<div class="temp">{weather['temp']}&#176;</div>
<div class="cond">{weather['condition']}</div>
<div class="wmeta">Feels {weather['feels']}&#176; &nbsp;&#183;&nbsp; Wind {weather['wind']} km/h &nbsp;&#183;&nbsp; Humidity {weather['humidity']}%</div>
<div class="wmeta">UV {weather['uv']} {weather['uv_label']} &nbsp;&#183;&nbsp; AQI {aqi['aqi']} {aqi['label']}</div>
<div class="wmeta">&#9788; {weather['sunrise']} &nbsp;&#183;&nbsp; &#9790; {weather['sunset']}</div>
<div class="rain-row">Rain: {rain_line}</div>
<h2>Rates</h2>
<div class="rate-row">USD/INR &nbsp;<strong>&#8377;{currency['usd_inr']}</strong> &nbsp;&nbsp; EUR/INR &nbsp;<strong>&#8377;{currency['eur_inr']}</strong></div>
<div class="wmeta">Claude resets in <strong>{claude_reset}</strong></div>"""

    # --- NEWS TAB ---
    news_list_html = ""
    for i, a in enumerate(articles):
        news_list_html += f'<div class="news-item" onclick="showArticle({i})"><div class="news-title">{a["title"]}</div><div class="news-src">{a["source"]}</div></div>\n'

    articles_html = ""
    for i, (a, body) in enumerate(zip(articles, article_bodies)):
        raw = (body or "").strip()
        content = raw if len(raw) > 50 else f"<p>{a['summary']}</p>"
        articles_html += f'<div class="article-view" id="article-{i}"><button class="back-btn" onclick="backToNews()">&#8592; News</button><div class="article-src">{a["source"]}</div><div class="article-title">{a["title"]}</div><div class="article-body">{content}</div></div>\n'

    news_html = f'<div class="news-list">{news_list_html}</div>{articles_html}'

    # --- CALENDAR TAB ---
    cal_html = ""
    for e in events:
        cal_html += f'<div class="event"><div class="event-title">{e["title"]}</div><div class="event-time">{e["time"]}</div></div>\n'
    if not cal_html:
        cal_html = '<div class="empty">No events today</div>'

    task_html = ""
    for t in reminders:
        task_html += f'<div class="task">&#9633; {t}</div>\n'
    if not task_html:
        task_html = '<div class="empty">No reminders</div>'

    cal_tab_html = f'<h2>Calendar</h2>{cal_html}<h2>Reminders</h2>{task_html}'

    # --- LIBRARY TAB ---
    lib_html = '<button class="exit-btn" onclick="exitToKOReader()">Open KOReader</button>\n'
    for b in books:
        pct = b['progress']
        if pct is not None:
            bar = f'<div class="progress-wrap"><div class="progress-fill" style="width:{pct}%"></div></div><span>{pct}%</span>'
        else:
            bar = '<span style="color:#bbb">not started</span>'
        lib_html += f'<div class="book-item"><div class="book-title">{b["title"]}</div><div class="book-meta"><span class="format-badge">{b["format"]}</span>{bar}</div></div>\n'
    if len(books) == 0:
        lib_html += '<div class="empty">No EPUB/MOBI files found</div>'

    # --- BOT TAB ---
    bot_html = f"""<div class="stat-row"><span class="stat-label">Emails today</span><span class="stat-val">{outreach['emails_today']}</span></div>
<div class="stat-row"><span class="stat-label">Last entry</span><div class="log-text">{outreach['last_action']}</div></div>"""

    js = """
function showTab(id) {
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  document.getElementById('nav-' + id).classList.add('active');
}
function showArticle(idx) {
  document.querySelector('.news-list').classList.add('hidden');
  document.querySelectorAll('.article-view').forEach(a => a.classList.remove('active'));
  document.getElementById('article-' + idx).classList.add('active');
}
function backToNews() {
  document.querySelectorAll('.article-view').forEach(a => a.classList.remove('active'));
  document.querySelector('.news-list').classList.remove('hidden');
}
function exitToKOReader() {
  var o = document.getElementById('exit-overlay');
  o.style.display = 'flex';
  var x = new XMLHttpRequest();
  x.open('GET', 'http://127.0.0.1:8765/exit', true);
  x.onerror = function() { o.querySelector('div').innerHTML = 'Bridge unreachable.<br>Use KUAL to switch.'; };
  x.send();
}
"""

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{CSS}</style>
</head>
<body>
<div id="exit-overlay"><div>Switching to KOReader&#8230;</div></div>
<div class="screen">
  <div id="tab-home" class="tab-content active">{home_html}</div>
  <div id="tab-news" class="tab-content">{news_html}</div>
  <div id="tab-cal" class="tab-content">{cal_tab_html}</div>
  <div id="tab-lib" class="tab-content"><h2>Library</h2>{lib_html}</div>
  <div id="tab-bot" class="tab-content"><h2>Outreach Bot</h2>{bot_html}</div>
  <nav>
    <button id="nav-home" class="active" onclick="showTab('home')">Home</button>
    <button id="nav-news" onclick="showTab('news')">News</button>
    <button id="nav-cal" onclick="showTab('cal')">Calendar</button>
    <button id="nav-lib" onclick="showTab('lib')">Library</button>
    <button id="nav-bot" onclick="showTab('bot')">Bot</button>
  </nav>
</div>
<script>{js}</script>
</body></html>"""

    (BASE_DIR / "dashboard.html").write_text(html, encoding="utf-8")
    return "dashboard.html"


def main():
    print("Fetching data...")

    weather = fetch_weather()
    print(f"  Weather: {weather['temp']}C {weather['condition']}")

    aqi = fetch_aqi()
    print(f"  AQI: {aqi['aqi']}")

    currency = fetch_currency()
    print(f"  USD/INR: {currency['usd_inr']}")

    articles = fetch_news()
    print(f"  News: {len(articles)} articles")

    print("  Fetching article bodies...")
    article_bodies = []
    for i, a in enumerate(articles, 1):
        body = fetch_article_body(a["url"])
        article_bodies.append(body)
        print(f"    [{i}] {a['title'][:50]} — {'ok' if body else 'summary only'}")

    events = fetch_calendar()
    print(f"  Calendar: {len(events)} events")

    reminders = fetch_reminders()
    print(f"  Reminders: {len(reminders)} items")

    outreach = fetch_outreach_status()
    print(f"  Outreach: {outreach['emails_today']} emails today")

    claude_reset = claude_reset_countdown()

    books = fetch_books()
    print(f"  Library: {len(books)} books")

    build_html(weather, aqi, currency, articles, events, reminders, outreach, claude_reset, article_bodies, books)
    print(f"\nGenerated dashboard.html in {BASE_DIR}")


if __name__ == "__main__":
    main()
