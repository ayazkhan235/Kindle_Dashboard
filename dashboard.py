#!/usr/bin/env python3
import os, subprocess, json, re
from datetime import datetime, timedelta
from pathlib import Path
import requests
import feedparser
from readability import Document
import config

BASE_DIR = Path(__file__).parent

CSS = """
body { font-family: Georgia, serif; font-size: 22px; background: white; color: black; margin: 0; padding: 20px; }
h1 { font-size: 16px; font-weight: bold; border-bottom: 2px solid black; padding-bottom: 6px; margin: 20px 0 12px 0; text-transform: uppercase; letter-spacing: 2px; }
.meta { font-size: 16px; color: #666; margin-bottom: 4px; }
.back { font-size: 18px; color: black; text-decoration: none; border: 1px solid black; padding: 6px 14px; display: inline-block; margin-bottom: 16px; }
.temp { font-size: 64px; font-weight: bold; }
.cond { font-size: 26px; }
.wmeta { font-size: 20px; color: #444; margin-top: 8px; }
.rain-row { margin: 10px 0; font-size: 18px; color: #333; }
.news-item { border-bottom: 1px solid #ccc; padding: 12px 0; }
.news-title { font-size: 22px; font-weight: bold; line-height: 1.35; text-decoration: none; color: black; display: block; }
.news-src { font-size: 16px; color: #777; margin-top: 4px; }
.event { padding: 12px 0; border-bottom: 1px solid #ddd; }
.event-title { font-size: 22px; font-weight: bold; }
.event-time { font-size: 18px; color: #555; margin-top: 4px; }
.task { padding: 10px 0; border-bottom: 1px solid #ddd; font-size: 22px; }
.stat { font-size: 22px; margin-bottom: 10px; }
.big { font-size: 48px; font-weight: bold; line-height: 1; }
.label { font-size: 16px; color: #666; text-transform: uppercase; letter-spacing: 1px; }
.log { font-size: 17px; color: #555; margin-top: 6px; word-break: break-word; }
.article-body { font-size: 22px; line-height: 1.6; }
.article-body p { margin: 0 0 14px; }
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
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        doc = Document(r.text)
        return doc.summary()
    except:
        return None


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


BASE = "file:///mnt/us/documents"

def page(title, body):
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body>{body}</body></html>"""

def make_home_body(weather, aqi, currency, articles, events, reminders, outreach, claude_reset, updated):
    # Rain forecast rows
    rain_rows = ""
    for t, pct in weather["rain_hours"]:
        hour = t.split("T")[1][:5] if "T" in t else t
        rain_rows += f'<span class="rain-hour"><div class="rain-pct">{pct}%</div><div>{hour}</div></span>'

    news_links = ""
    for i, a in enumerate(articles, 1):
        news_links += f'<a class="news-link" href="article{i}.xhtml">{a["title"]}<div class="news-src">{a["source"]}</div></a>\n'

    cal_rows = ""
    for e in events:
        cal_rows += f'<div class="event"><div>{e["title"]}</div><div class="event-time">{e["time"]}</div></div>\n'
    if not cal_rows:
        cal_rows = '<div class="event">No events today</div>'

    task_rows = ""
    for t in reminders:
        task_rows += f'<div class="task">&#9633; {t}</div>\n'
    if not task_rows:
        task_rows = '<div class="task">No reminders</div>'

    return f"""<div class="meta">{updated}</div>

<h1>Weather &#8212; Mumbai</h1>
<div class="weather-row">
  <span class="temp">{weather['temp']}&#176;</span>
  <span class="cond">{weather['condition']}</span>
</div>
<div class="weather-meta">
  Feels {weather['feels']}&#176; &nbsp;&#183;&nbsp; Wind {weather['wind']} km/h &nbsp;&#183;&nbsp; Humidity {weather['humidity']}%
</div>
<div class="weather-meta">
  UV {weather['uv']} {weather['uv_label']} &nbsp;&#183;&nbsp; AQI {aqi['aqi']} {aqi['label']}
</div>
<div class="weather-meta">
  Sunrise {weather['sunrise']} &nbsp;&#183;&nbsp; Sunset {weather['sunset']}
</div>
<div class="rain-bar-wrap">{rain_rows}</div>

<div class="heavy-hr"/>

<h1>News</h1>
{news_links}

<div class="heavy-hr"/>

<h1>Calendar</h1>
{cal_rows}

<div class="heavy-hr"/>

<h1>Reminders</h1>
{task_rows}

<div class="heavy-hr"/>

<h1>Outreach Bot</h1>
<div class="stat-row"><span class="label">Emails today</span><br/><span class="val">{outreach['emails_today']}</span></div>
<div class="stat-row"><span class="label">Last entry</span><br/>{outreach['last_action']}</div>

<div class="heavy-hr"/>

<h1>Rates &amp; Claude</h1>
<div class="stat-row">USD/INR <span class="val">&#8377;{currency['usd_inr']}</span> &nbsp;&#183;&nbsp; EUR/INR <span class="val">&#8377;{currency['eur_inr']}</span></div>
<div class="stat-row">Claude resets in <span class="val">{claude_reset}</span></div>"""


def make_article_html(article, body_html, index, total):
    raw = body_html.strip() if body_html else ""
    clean_body = raw if len(raw) > 50 else f"<p>{article['summary']}</p>"
    body = f"""<a class="back" href="{BASE}/dashboard.html">&#8592; Dashboard</a>
<div class="label">{article['source']} &nbsp;&#183;&nbsp; Article {index} of {total}</div>
<h1>{article['title']}</h1>
<hr/>
<div class="article-body">{clean_body}</div>"""
    return page(article['title'], body)


def build_html(weather, aqi, currency, articles, events, reminders, outreach, claude_reset, article_bodies):
    updated = datetime.now().strftime("%d %b %Y, %I:%M %p")

    # Rain forecast line
    rain_parts = []
    for t, pct in weather["rain_hours"]:
        hour = t.split("T")[1][:5] if "T" in t else t
        rain_parts.append(f"{hour}&nbsp;{pct}%")
    rain_line = " &nbsp;|&nbsp; ".join(rain_parts)

    # News links
    news_html = ""
    for i, a in enumerate(articles, 1):
        news_html += f"""<div class="news-item">
<a class="news-title" href="{BASE}/news/article-{i}.html">{a['title']}</a>
<div class="news-src">{a['source']}</div>
</div>\n"""

    # Calendar
    cal_html = ""
    for e in events:
        cal_html += f'<div class="event"><div class="event-title">{e["title"]}</div><div class="event-time">{e["time"]}</div></div>\n'
    if not cal_html:
        cal_html = '<div class="event">No events today</div>'

    # Tasks
    task_html = ""
    for t in reminders:
        task_html += f'<div class="task">&#9633; {t}</div>\n'
    if not task_html:
        task_html = '<div class="task">No reminders</div>'

    home_body = f"""<div class="meta">{updated}</div>

<h1>Weather &#8212; Mumbai</h1>
<div><span class="temp">{weather['temp']}&#176;</span></div>
<div class="wmeta">{weather['condition']} &nbsp;&#183;&nbsp; Feels {weather['feels']}&#176; &nbsp;&#183;&nbsp; Wind {weather['wind']} km/h</div>
<div class="wmeta">Humidity {weather['humidity']}% &nbsp;&#183;&nbsp; UV {weather['uv']} {weather['uv_label']} &nbsp;&#183;&nbsp; AQI {aqi['aqi']} {aqi['label']}</div>
<div class="wmeta">Sunrise {weather['sunrise']} &nbsp;&#183;&nbsp; Sunset {weather['sunset']}</div>
<div class="rain-row">Rain next 8h: {rain_line}</div>

<h1>News</h1>
{news_html}
<h1>Calendar</h1>
{cal_html}
<h1>Reminders</h1>
{task_html}
<h1>Outreach Bot</h1>
<div class="stat"><span class="label">Emails today</span><br/><span class="big">{outreach['emails_today']}</span></div>
<div class="label">Last entry</div>
<div class="log">{outreach['last_action']}</div>

<h1>Rates &amp; Claude</h1>
<div class="stat">USD/INR <strong>&#8377;{currency['usd_inr']}</strong> &nbsp;&nbsp; EUR/INR <strong>&#8377;{currency['eur_inr']}</strong></div>
<div class="stat">Claude resets in <strong>{claude_reset}</strong></div>"""

    pages = {"dashboard.html": page("Dashboard", home_body)}

    news_dir = BASE_DIR / "news"
    news_dir.mkdir(exist_ok=True)
    for i, (article, body) in enumerate(zip(articles, article_bodies), 1):
        pages[f"news/article-{i}.html"] = make_article_html(article, body, i, len(articles))

    for filename, content in pages.items():
        (BASE_DIR / filename).write_text(content, encoding="utf-8")

    return list(pages.keys())


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

    files = build_html(weather, aqi, currency, articles, events, reminders, outreach, claude_reset, article_bodies)
    print(f"\nGenerated {len(files)} files in {BASE_DIR}")


if __name__ == "__main__":
    main()
