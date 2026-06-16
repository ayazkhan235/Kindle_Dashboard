#!/usr/bin/env python3
"""
Generates a beautiful e-ink PNG dashboard for Kindle Paperwhite 7th Gen.
Screen: 1072 x 1448 px
"""
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from pathlib import Path
import requests
import feedparser
import subprocess
import os
import config

BASE_DIR = Path(__file__).parent
OUT_PATH = BASE_DIR / "dashboard.png"

W, H = 1072, 1448
PAD = 48
COL = W - PAD * 2

BLACK = 0
WHITE = 255
GRAY = 160
LIGHT = 210

# Fonts
def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()

HELVETICA = "/System/Library/Fonts/HelveticaNeue.ttc"
TIMES     = "/System/Library/Fonts/Times.ttc"

F_TINY    = font(HELVETICA, 22)
F_SMALL   = font(HELVETICA, 28)
F_MED     = font(HELVETICA, 34)
F_LABEL   = font(HELVETICA, 24)
F_BOLD    = font(HELVETICA, 36)
F_TEMP    = font(HELVETICA, 120)
F_HEAD    = font(HELVETICA, 30)
F_NEWS    = font(TIMES, 32)
F_SECTION = font(HELVETICA, 22)


# ── Data fetchers ──────────────────────────────────────────────────────────────

def fetch_weather():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": config.MUMBAI_LAT, "longitude": config.MUMBAI_LON,
        "current": "temperature_2m,apparent_temperature,weathercode,windspeed_10m,relativehumidity_2m,uv_index",
        "hourly": "precipitation_probability",
        "daily": "sunrise,sunset",
        "timezone": "Asia/Kolkata", "forecast_days": 1,
    }
    try:
        d = requests.get(url, params=params, timeout=10).json()
        c = d["current"]; h = d["hourly"]; daily = d["daily"]
        now_h = datetime.now().hour
        rain = list(zip(h["time"][now_h:now_h+6], h["precipitation_probability"][now_h:now_h+6]))
        return {
            "temp": round(c["temperature_2m"]),
            "feels": round(c["apparent_temperature"]),
            "condition": wcode_label(c["weathercode"]),
            "wind": round(c["windspeed_10m"]),
            "humidity": c.get("relativehumidity_2m", "--"),
            "uv": round(c.get("uv_index", 0)),
            "rain": rain,
            "sunrise": daily["sunrise"][0].split("T")[1] if daily.get("sunrise") else "--",
            "sunset":  daily["sunset"][0].split("T")[1]  if daily.get("sunset")  else "--",
        }
    except:
        return {"temp": "--", "feels": "--", "condition": "Unavailable", "wind": "--",
                "humidity": "--", "uv": "--", "rain": [], "sunrise": "--", "sunset": "--"}

def wcode_label(c):
    m = {0:"Clear sky",1:"Mostly clear",2:"Partly cloudy",3:"Overcast",
         45:"Foggy",48:"Foggy",51:"Light drizzle",53:"Drizzle",55:"Heavy drizzle",
         61:"Light rain",63:"Rain",65:"Heavy rain",80:"Showers",81:"Showers",
         82:"Heavy showers",95:"Thunderstorm",99:"Thunderstorm"}
    return m.get(c, f"Code {c}")

def fetch_aqi():
    try:
        d = requests.get(f"https://api.waqi.info/feed/mumbai/?token={config.WAQI_TOKEN}", timeout=10).json()
        if d["status"] == "ok":
            aqi = d["data"]["aqi"]
            lbl = ["Good","Moderate","Sensitive","Unhealthy","Very Unhealthy","Hazardous"]
            idx = [50,100,150,200,300]
            label = lbl[next((i for i,v in enumerate(idx) if aqi<=v), 5)]
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
    for feed_url in config.RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for e in feed.entries[:4]:
                articles.append({"title": e.get("title",""), "source": feed.feed.get("title","")})
                if len(articles) >= 6: break
        except: pass
        if len(articles) >= 6: break
    return articles[:6]

def fetch_calendar():
    try:
        r = subprocess.run(
            ["icalBuddy","-n","-nrd","-b","• ","-iep","title,datetime","-po","title,datetime","eventsToday"],
            capture_output=True, text=True, timeout=15)
        lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
        events, cur = [], {}
        for line in lines:
            if line.startswith("•"):
                if cur: events.append(cur)
                cur = {"title": line[1:].strip(), "time": ""}
            elif cur:
                cur["time"] = line
        if cur: events.append(cur)
        return events[:4]
    except: return []

def fetch_reminders():
    try:
        r = subprocess.run(["reminders","show","all"], capture_output=True, text=True, timeout=10)
        return [l.strip().lstrip("•-* ") for l in r.stdout.splitlines() if l.strip()][:5]
    except: return []

def fetch_outreach():
    try:
        log = config.OUTREACH_LOG
        if not os.path.exists(log):
            cands = list(Path("/Users/ayazkhan/outreach_bot").rglob("*.log"))
            if cands: log = str(cands[0])
            else: return {"count": "--", "last": "log not found"}
        lines = subprocess.run(["tail","-50",log], capture_output=True, text=True).stdout.splitlines()
        today = datetime.now().strftime("%Y-%m-%d")
        tl = [l for l in lines if today in l]
        sent = sum(1 for l in tl if "sent" in l.lower() or "email" in l.lower())
        last = (tl[-1] if tl else (lines[-1] if lines else ""))[-60:]
        return {"count": sent, "last": last}
    except Exception as e:
        return {"count": "--", "last": str(e)[:60]}

def claude_reset():
    from datetime import datetime
    now = datetime.now()
    day = config.CLAUDE_BILLING_DAY
    nxt = now.replace(day=day, hour=0, minute=0, second=0, microsecond=0)
    if nxt <= now:
        nxt = nxt.replace(month=now.month+1 if now.month<12 else 1,
                          year=now.year if now.month<12 else now.year+1)
    d = nxt - now
    return f"{d.days}d {d.seconds//3600}h"


# ── Drawing helpers ────────────────────────────────────────────────────────────

def text(draw, xy, s, f, fill=BLACK, anchor="la"):
    draw.text(xy, str(s), font=f, fill=fill, anchor=anchor)

def hline(draw, y, x0=PAD, x1=W-PAD, width=1, fill=BLACK):
    draw.line([(x0, y), (x1, y)], fill=fill, width=width)

def section_header(draw, y, label):
    text(draw, (PAD, y), label, F_SECTION, fill=GRAY)
    hline(draw, y+28, fill=LIGHT)
    return y + 42


# ── Main render ────────────────────────────────────────────────────────────────

def render(weather, aqi, currency, news, events, reminders, outreach, claude):
    img  = Image.new("L", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    now = datetime.now()
    updated = now.strftime("%-I:%M %p")
    datestr = now.strftime("%a %-d %b %Y")

    y = 36

    # ── HEADER ──────────────────────────────────────────────────────────────
    text(draw, (PAD, y),   "KINDLE DASHBOARD",   F_SECTION, fill=GRAY)
    text(draw, (W-PAD, y), f"{datestr}  {updated}", F_SECTION, fill=GRAY, anchor="ra")
    y += 32
    hline(draw, y, width=2)
    y += 32

    # ── WEATHER ─────────────────────────────────────────────────────────────
    # Big temp
    text(draw, (PAD, y), f"{weather['temp']}°", F_TEMP)
    # Condition right of temp — measure temp width
    bbox = draw.textbbox((0,0), f"{weather['temp']}°", font=F_TEMP)
    tx = PAD + bbox[2] + 24
    text(draw, (tx, y+14), weather["condition"], F_BOLD)
    text(draw, (tx, y+60), f"Feels {weather['feels']}°  ·  Wind {weather['wind']} km/h", F_MED, fill=GRAY)
    text(draw, (tx, y+100), f"Humidity {weather['humidity']}%  ·  UV {weather['uv']}  ·  AQI {aqi['aqi']} {aqi['label']}", F_SMALL, fill=GRAY)
    text(draw, (tx, y+136), f"Sunrise {weather['sunrise']}  ·  Sunset {weather['sunset']}", F_SMALL, fill=GRAY)
    y += 175

    # Rain bar
    if weather["rain"]:
        bar_w = COL // len(weather["rain"])
        for i, (t, pct) in enumerate(weather["rain"]):
            hr = t.split("T")[1][:5] if "T" in t else t
            bx = PAD + i * bar_w
            # bar background
            draw.rectangle([bx, y+30, bx+bar_w-4, y+50], fill=LIGHT)
            # fill
            fill_w = int((bar_w-4) * pct / 100)
            if fill_w > 0:
                draw.rectangle([bx, y+30, bx+fill_w, y+50], fill=GRAY)
            text(draw, (bx + bar_w//2, y+14), hr[:-3], F_TINY, fill=GRAY, anchor="ma")
            text(draw, (bx + bar_w//2, y+56), f"{pct}%", F_TINY, fill=GRAY, anchor="ma")
        y += 80

    y += 16
    hline(draw, y, width=2)
    y += 28

    # ── NEWS ─────────────────────────────────────────────────────────────────
    y = section_header(draw, y, "NEWS")
    for i, a in enumerate(news):
        # bullet
        draw.ellipse([PAD, y+10, PAD+8, y+18], fill=BLACK)
        # title — wrap if long
        title = a["title"]
        if len(title) > 62:
            title = title[:62] + "…"
        text(draw, (PAD+20, y), title, F_NEWS)
        y += 40
        if i < len(news)-1:
            hline(draw, y-4, fill=LIGHT)
    y += 8
    hline(draw, y, width=2)
    y += 28

    # ── CALENDAR + REMINDERS ─────────────────────────────────────────────────
    col2 = (COL - 40) // 2
    cal_x  = PAD
    task_x = PAD + col2 + 40

    y = section_header(draw, y, "CALENDAR")
    # re-draw reminders label at same y
    ry_start = y - 42
    text(draw, (task_x, ry_start), "REMINDERS", F_SECTION, fill=GRAY)

    row_y = y
    for e in events[:4]:
        time_str = e["time"].split(" at ")[-1] if " at " in e["time"] else e["time"]
        time_str = time_str[:8]
        text(draw, (cal_x, row_y), time_str, F_SMALL, fill=GRAY)
        title = e["title"][:26] if len(e["title"]) > 26 else e["title"]
        text(draw, (cal_x, row_y+30), title, F_MED)
        row_y += 72

    row_y2 = y
    for t in reminders[:4]:
        draw.rectangle([task_x, row_y2+8, task_x+14, row_y2+22], outline=BLACK, width=2)
        txt = t[:28] if len(t) > 28 else t
        text(draw, (task_x+24, row_y2), txt, F_MED)
        row_y2 += 56

    y = max(row_y, row_y2) + 16
    hline(draw, y, width=2)
    y += 28

    # ── OUTREACH + RATES ─────────────────────────────────────────────────────
    y = section_header(draw, y, "OUTREACH BOT")
    text(draw, (W-PAD, y-42), "RATES", F_SECTION, fill=GRAY, anchor="ra")

    # Left: outreach
    text(draw, (PAD, y), str(outreach["count"]), F_TEMP)
    bbox2 = draw.textbbox((0,0), str(outreach["count"]), font=F_TEMP)
    text(draw, (PAD + bbox2[2] + 14, y+50), "emails today", F_MED, fill=GRAY)

    # Right: rates
    rx = W - PAD
    text(draw, (rx, y),    f"USD  ₹{currency['usd']}", F_BOLD, anchor="ra")
    text(draw, (rx, y+52), f"EUR  ₹{currency['eur']}", F_BOLD, anchor="ra")

    y += 130
    hline(draw, y, width=2)
    y += 24

    # ── FOOTER: Claude ────────────────────────────────────────────────────────
    text(draw, (PAD, y+10), f"Claude resets in  {claude}", F_MED, fill=GRAY)
    text(draw, (W-PAD, y+10), f"Updated {updated}", F_SMALL, fill=LIGHT, anchor="ra")

    # Save
    img.save(OUT_PATH, "PNG")
    print(f"Saved: {OUT_PATH}")
    return OUT_PATH


def main():
    print("Fetching data...")
    weather  = fetch_weather();  print(f"  Weather: {weather['temp']}°C")
    aqi      = fetch_aqi();      print(f"  AQI: {aqi['aqi']}")
    currency = fetch_currency(); print(f"  USD/INR: {currency['usd']}")
    news     = fetch_news();     print(f"  News: {len(news)} articles")
    events   = fetch_calendar(); print(f"  Calendar: {len(events)} events")
    reminders= fetch_reminders();print(f"  Reminders: {len(reminders)}")
    outreach = fetch_outreach(); print(f"  Outreach: {outreach['count']} emails")
    claude   = claude_reset();   print(f"  Claude reset: {claude}")
    render(weather, aqi, currency, news, events, reminders, outreach, claude)

if __name__ == "__main__":
    main()
