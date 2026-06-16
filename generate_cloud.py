#!/usr/bin/env python3
"""
Cloud version — runs on GitHub Actions.
No AppleScript, no local files. Only API-based data.
"""
import os, re
from datetime import datetime
from pathlib import Path
import requests
import feedparser

MUMBAI_LAT = 19.0760
MUMBAI_LON = 72.8777
WAQI_TOKEN = os.environ.get("WAQI_TOKEN", "")
CLAUDE_BILLING_DAY = int(os.environ.get("CLAUDE_BILLING_DAY", "1"))
RSS_FEEDS = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.reuters.com/reuters/worldNews",
]
MAX_ARTICLES = 8
OUT_DIR = Path("docs")
OUT_DIR.mkdir(exist_ok=True)


def fetch_weather():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": MUMBAI_LAT, "longitude": MUMBAI_LON,
        "current": "temperature_2m,apparent_temperature,weathercode,windspeed_10m,relativehumidity_2m,uv_index",
        "hourly": "precipitation_probability",
        "daily": "sunrise,sunset",
        "timezone": "Asia/Kolkata", "forecast_days": 1,
    }
    try:
        d = requests.get(url, params=params, timeout=10).json()
        c = d["current"]; h = d["hourly"]; daily = d["daily"]
        now_h = datetime.now().hour
        rain = list(zip(h["time"][now_h:now_h+8], h["precipitation_probability"][now_h:now_h+8]))
        uv = round(c.get("uv_index", 0))
        return {
            "temp": round(c["temperature_2m"]),
            "feels": round(c["apparent_temperature"]),
            "condition": wcode_label(c["weathercode"]),
            "wind": round(c["windspeed_10m"]),
            "humidity": c.get("relativehumidity_2m", "--"),
            "uv": uv, "uv_label": uv_label(uv),
            "rain": rain,
            "sunrise": daily["sunrise"][0].split("T")[1] if daily.get("sunrise") else "--",
            "sunset":  daily["sunset"][0].split("T")[1]  if daily.get("sunset")  else "--",
        }
    except Exception as e:
        return {"temp":"--","feels":"--","condition":"Unavailable","wind":"--",
                "humidity":"--","uv":"--","uv_label":"","rain":[],"sunrise":"--","sunset":"--"}

def wcode_label(c):
    m = {0:"Clear sky",1:"Mostly clear",2:"Partly cloudy",3:"Overcast",
         45:"Foggy",48:"Foggy",51:"Light drizzle",53:"Drizzle",55:"Heavy drizzle",
         61:"Light rain",63:"Rain",65:"Heavy rain",80:"Showers",82:"Heavy showers",
         95:"Thunderstorm",99:"Thunderstorm"}
    return m.get(c, "")

def uv_label(uv):
    if not isinstance(uv, int): return ""
    return ["Low","Low","Low","Moderate","Moderate","Moderate","High","High","Very High","Very High","Very High","Extreme"][min(uv,11)]

def fetch_aqi():
    try:
        d = requests.get(f"https://api.waqi.info/feed/mumbai/?token={WAQI_TOKEN}", timeout=10).json()
        if d["status"] == "ok":
            aqi = d["data"]["aqi"]
            labels = ["Good","Moderate","Sensitive","Unhealthy","Very Unhealthy","Hazardous"]
            thresholds = [50,100,150,200,300]
            label = labels[next((i for i,v in enumerate(thresholds) if aqi<=v), 5)]
            return {"aqi": aqi, "label": label}
    except: pass
    return {"aqi": "--", "label": ""}

def fetch_currency():
    try:
        d = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10).json()
        r = d.get("rates", {})
        usd = round(r.get("INR", 0), 2)
        eur = round(usd / r.get("EUR", 1), 2) if r.get("EUR") else "--"
        return {"usd": usd, "eur": eur}
    except:
        return {"usd": "--", "eur": "--"}

def fetch_news():
    articles = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for e in feed.entries[:5]:
                articles.append({
                    "title": e.get("title", ""),
                    "source": feed.feed.get("title", ""),
                    "url": e.get("link", ""),
                    "summary": re.sub(r'<[^>]+>', '', e.get("summary", ""))[:200],
                })
                if len(articles) >= MAX_ARTICLES: break
        except: pass
        if len(articles) >= MAX_ARTICLES: break
    return articles[:MAX_ARTICLES]

def claude_reset():
    now = datetime.now()
    day = CLAUDE_BILLING_DAY
    nxt = now.replace(day=day, hour=0, minute=0, second=0, microsecond=0)
    if nxt <= now:
        m, y = (now.month % 12) + 1, now.year + (1 if now.month == 12 else 0)
        nxt = nxt.replace(year=y, month=m)
    d = nxt - now
    return f"{d.days}d {d.seconds//3600}h"

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: Georgia, serif;
  font-size: 22px;
  background: #fff;
  color: #000;
  padding: 28px 32px;
  max-width: 1072px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  border-bottom: 3px solid #000;
  padding-bottom: 10px;
  margin-bottom: 24px;
}
.header-title { font-size: 14px; letter-spacing: 3px; text-transform: uppercase; color: #999; }
.header-date  { font-size: 14px; color: #999; }

/* Weather */
.weather { margin-bottom: 24px; }
.temp-row { display: flex; align-items: baseline; gap: 18px; margin-bottom: 8px; }
.temp { font-size: 96px; font-weight: bold; line-height: 1; letter-spacing: -4px; }
.condition { font-size: 30px; color: #333; }
.wmeta { font-size: 19px; color: #555; margin-top: 5px; }
.rain-row { margin-top: 10px; }
.rain-item { display: inline-block; text-align: center; margin-right: 14px; }
.rain-time { font-size: 14px; color: #aaa; display: block; }
.rain-pct  { font-size: 18px; font-weight: bold; color: #333; }
.rain-hi   { color: #000; }

/* Divider */
.divider { border: none; border-top: 1px solid #ccc; margin: 20px 0; }
.divider-heavy { border-top: 2px solid #000; margin: 22px 0; }

/* Section label */
.section-label {
  font-size: 13px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: #aaa;
  margin-bottom: 14px;
}

/* News */
.news-item { padding: 11px 0; border-bottom: 1px solid #e0e0e0; }
.news-item:last-child { border-bottom: none; }
.news-title { font-size: 23px; line-height: 1.35; font-weight: bold; color: #111; text-decoration: none; display: block; }
.news-title:hover { text-decoration: underline; }
.news-src { font-size: 14px; color: #aaa; margin-top: 3px; }

/* Two columns */
.two-col { display: table; width: 100%; border-collapse: collapse; }
.col-left  { display: table-cell; width: 55%; vertical-align: top; padding-right: 28px; }
.col-right { display: table-cell; width: 45%; vertical-align: top; border-left: 1px solid #e0e0e0; padding-left: 28px; }

/* Calendar */
.event { padding: 9px 0; border-bottom: 1px solid #eee; }
.event:last-child { border-bottom: none; }
.event-title { font-size: 21px; font-weight: bold; }
.event-time  { font-size: 16px; color: #777; margin-top: 2px; }

/* Reminders */
.task { padding: 8px 0; border-bottom: 1px solid #eee; font-size: 20px; }
.task:last-child { border-bottom: none; }
.task::before { content: '\\25A1  '; font-size: 16px; }

/* Bottom strip */
.bottom-strip { display: table; width: 100%; margin-top: 4px; }
.bot-cell  { display: table-cell; vertical-align: top; width: 40%; }
.rate-cell { display: table-cell; vertical-align: top; width: 30%; padding-left: 20px; border-left: 1px solid #e0e0e0; }
.claude-cell { display: table-cell; vertical-align: top; width: 30%; padding-left: 20px; border-left: 1px solid #e0e0e0; }

.big-num { font-size: 64px; font-weight: bold; letter-spacing: -2px; line-height: 1; }
.rate-val { font-size: 26px; font-weight: bold; margin-top: 4px; }
.updated-stamp { font-size: 13px; color: #ccc; margin-top: 18px; }
"""

def build_html(weather, aqi, currency, news, claude):
    now = datetime.now()
    updated = now.strftime("%-I:%M %p")
    datestr  = now.strftime("%a, %-d %b %Y")

    rain_html = ""
    for t, pct in weather["rain"]:
        hr = t.split("T")[1][:5] if "T" in t else t
        hi = ' rain-hi' if pct >= 50 else ''
        rain_html += f'<span class="rain-item"><span class="rain-time">{hr}</span><span class="rain-pct{hi}">{pct}%</span></span>'

    news_html = ""
    for a in news:
        news_html += f"""<div class="news-item">
  <a class="news-title" href="{a['url']}" target="_blank">{a['title']}</a>
  <div class="news-src">{a['source']}</div>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=1072">
<title>Kindle Dashboard</title>
<style>{CSS}</style>
</head>
<body>

<div class="header">
  <span class="header-title">Dashboard &mdash; Mumbai</span>
  <span class="header-date">{datestr} &nbsp;&bull;&nbsp; {updated} IST</span>
</div>

<div class="weather">
  <div class="temp-row">
    <span class="temp">{weather['temp']}&deg;</span>
    <span class="condition">{weather['condition']}</span>
  </div>
  <div class="wmeta">Feels {weather['feels']}&deg; &nbsp;&bull;&nbsp; Wind {weather['wind']} km/h &nbsp;&bull;&nbsp; Humidity {weather['humidity']}%</div>
  <div class="wmeta">UV {weather['uv']} {weather['uv_label']} &nbsp;&bull;&nbsp; AQI {aqi['aqi']} {aqi['label']} &nbsp;&bull;&nbsp; Sunrise {weather['sunrise']} &nbsp;&bull;&nbsp; Sunset {weather['sunset']}</div>
  <div class="rain-row">{rain_html}</div>
</div>

<hr class="divider-heavy"/>

<div class="section-label">Today&rsquo;s News</div>
{news_html}

<hr class="divider-heavy"/>

<div class="two-col">
  <div class="col-left">
    <div class="section-label">Rates</div>
    <div class="wmeta">USD / INR &nbsp; <strong style="font-size:26px">&thinsp;&#8377;{currency['usd']}</strong></div>
    <div class="wmeta" style="margin-top:8px">EUR / INR &nbsp; <strong style="font-size:26px">&thinsp;&#8377;{currency['eur']}</strong></div>
  </div>
  <div class="col-right">
    <div class="section-label">Claude</div>
    <div class="wmeta">Resets in &nbsp;<strong style="font-size:24px">{claude}</strong></div>
  </div>
</div>

<div class="updated-stamp">Last updated: {datestr} {updated} IST &mdash; auto-refreshes hourly</div>

</body>
</html>"""


def main():
    print("Fetching data...")
    weather  = fetch_weather();  print(f"  {weather['temp']}°C {weather['condition']}")
    aqi      = fetch_aqi();      print(f"  AQI {aqi['aqi']}")
    currency = fetch_currency(); print(f"  USD/INR {currency['usd']}")
    news     = fetch_news();     print(f"  {len(news)} articles")
    claude   = claude_reset();   print(f"  Claude resets {claude}")

    html = build_html(weather, aqi, currency, news, claude)
    (OUT_DIR / "dashboard.html").write_text(html, encoding="utf-8")
    (OUT_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"  Written to docs/")

if __name__ == "__main__":
    main()
