#!/usr/bin/env python3
"""Cloud dashboard generator — runs on GitHub Actions hourly.
Reads private_data.json (pushed by Mac) + algo_data.json for local data.
Fetches weather/news/HN/GitHub/pharma-news live from cloud APIs.
Outputs docs/index.html → served via GitHub Pages → Kindle loads it."""
import os, re, json, time
from datetime import datetime
from pathlib import Path
import requests
import feedparser

# ── config ──────────────────────────────────────────────────────────────────
MUMBAI_LAT       = 19.0760
MUMBAI_LON       = 72.8777
WAQI_TOKEN       = os.environ.get("WAQI_TOKEN", "demo")
CLAUDE_BILLING_DAY = int(os.environ.get("CLAUDE_BILLING_DAY", "1"))
GITHUB_TOKEN     = os.environ.get("GITHUB_TOKEN", "")
GITHUB_USERNAME  = os.environ.get("GITHUB_USERNAME", "ayazkhan235")
RSS_FEEDS        = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.reuters.com/reuters/worldNews",
]
PHARMA_FEEDS = [
    "https://news.google.com/rss/search?q=chlorohexidine+pharma+price&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=pharma+raw+material+india+bulk+drug&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=pharmaceutical+freight+shipping+india&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=API+active+pharmaceutical+ingredient+price+2026&hl=en&gl=US&ceid=US:en",
]
OUT_DIR = Path("docs")
OUT_DIR.mkdir(exist_ok=True)


# ── local data (from Mac-pushed JSON files) ──────────────────────────────────
def load_private_data():
    p = Path("private_data.json")
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {}

def load_algo_data():
    p = Path("algo_data.json")
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {}


# ── cloud fetchers ───────────────────────────────────────────────────────────
def fetch_weather():
    params = {
        "latitude": MUMBAI_LAT, "longitude": MUMBAI_LON,
        "current": "temperature_2m,apparent_temperature,weathercode,precipitation,"
                   "windspeed_10m,relativehumidity_2m,uv_index",
        "hourly": "temperature_2m,precipitation_probability,precipitation,weathercode",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "Asia/Kolkata", "forecast_days": 2,
    }
    try:
        j = requests.get("https://api.open-meteo.com/v1/forecast",
                         params=params, timeout=10).json()
        cur, hr, dy = j["current"], j["hourly"], j["daily"]
        now_h = datetime.now().hour
        sl = slice(now_h, now_h + 8)
        hours = [{"time": t.split("T")[1][:5], "temp": round(temp), "pop": pp}
                 for t, temp, pp in zip(hr["time"][sl],
                                        hr["temperature_2m"][sl],
                                        hr["precipitation_probability"][sl])]
        uv = round(cur.get("uv_index", 0))
        return {
            "temp": round(cur["temperature_2m"]),
            "feels": round(cur["apparent_temperature"]),
            "condition": wcode_label(cur["weathercode"]),
            "wind": round(cur["windspeed_10m"]),
            "humidity": cur.get("relativehumidity_2m", "--"),
            "uv": uv, "uv_label": uv_label(uv),
            "hi": round(dy["temperature_2m_max"][0]),
            "lo": round(dy["temperature_2m_min"][0]),
            "rain_sum": dy["precipitation_sum"][0],
            "hours": hours,
        }
    except Exception:
        return {"temp": "--", "feels": "--", "condition": "Unavailable",
                "wind": "--", "humidity": "--", "uv": "--", "uv_label": "",
                "hi": "--", "lo": "--", "rain_sum": 0, "hours": []}


def wcode_label(c):
    m = {0:"Clear",1:"Mostly clear",2:"Partly cloudy",3:"Overcast",
         45:"Foggy",48:"Foggy",51:"Light drizzle",53:"Drizzle",55:"Heavy drizzle",
         61:"Light rain",63:"Rain",65:"Heavy rain",80:"Showers",82:"Heavy showers",
         95:"Thunderstorm",99:"Thunderstorm"}
    return m.get(c, f"Code {c}")

def uv_label(uv):
    if not isinstance(uv, (int, float)): return ""
    if uv <= 2: return "Low"
    if uv <= 5: return "Moderate"
    if uv <= 7: return "High"
    if uv <= 10: return "Very High"
    return "Extreme"


def fetch_aqi():
    try:
        d = requests.get(f"https://api.waqi.info/feed/mumbai/?token={WAQI_TOKEN}",
                         timeout=10).json()
        if d["status"] == "ok":
            aqi = d["data"]["aqi"]
            labels = ["Good","Moderate","Sensitive","Unhealthy","Very Unhealthy","Hazardous"]
            thresholds = [50, 100, 150, 200, 300]
            label = labels[next((i for i, v in enumerate(thresholds) if aqi <= v), 5)]
            return {"aqi": aqi, "label": label}
    except Exception:
        pass
    return {"aqi": "--", "label": ""}


def fetch_currency():
    try:
        d = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10).json()
        r = d.get("rates", {})
        usd = round(r.get("INR", 0), 2)
        eur = round(usd / r.get("EUR", 1), 2) if r.get("EUR") else "--"
        return {"usd_inr": usd, "eur_inr": eur}
    except Exception:
        return {"usd_inr": "--", "eur_inr": "--"}


def fetch_news(max_articles=6):
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:4]:
                articles.append({
                    "title": e.get("title", ""),
                    "source": feed.feed.get("title", ""),
                    "url": e.get("link", ""),
                    "summary": re.sub(r'<[^>]+>', '', e.get("summary", ""))[:300],
                })
                if len(articles) >= max_articles:
                    break
        except Exception:
            pass
        if len(articles) >= max_articles:
            break
    return articles[:max_articles]


def fetch_pharma_news(max_items=5):
    items = []
    seen = set()
    for url in PHARMA_FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:3]:
                title = e.get("title", "").strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                items.append({
                    "title": title,
                    "source": e.get("source", {}).get("title", "Google News") if hasattr(e.get("source", {}), "get") else "Google News",
                    "date": e.get("published", "")[:16],
                })
                if len(items) >= max_items:
                    break
        except Exception:
            pass
        if len(items) >= max_items:
            break
    return items[:max_items]


def fetch_hn_top(n=5):
    try:
        ids = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=8
        ).json()[:n]
        stories = []
        for sid in ids:
            try:
                s = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5
                ).json()
                stories.append({"title": s.get("title", ""),
                                 "score": s.get("score", 0),
                                 "by": s.get("by", "")})
            except Exception:
                pass
        return stories
    except Exception:
        return []


def fetch_github():
    if not GITHUB_TOKEN:
        return {"repos": [], "pr_count": "--", "issue_count": "--", "username": GITHUB_USERNAME}
    headers = {"Authorization": f"token {GITHUB_TOKEN}",
               "Accept": "application/vnd.github.v3+json"}
    try:
        repos_raw = requests.get(
            "https://api.github.com/user/repos?sort=pushed&per_page=6&type=owner",
            headers=headers, timeout=8).json()
        repos = [{"name": r["name"],
                  "pushed": (r.get("pushed_at") or "")[:10],
                  "private": r.get("private", False)}
                 for r in repos_raw if isinstance(r, dict)][:6]
        prs = requests.get(
            f"https://api.github.com/search/issues?q=is:pr+is:open+author:{GITHUB_USERNAME}",
            headers=headers, timeout=8).json()
        pr_count = prs.get("total_count", 0)
        issues_raw = requests.get(
            "https://api.github.com/issues?state=open&per_page=10",
            headers=headers, timeout=8).json()
        issue_count = len(issues_raw) if isinstance(issues_raw, list) else 0
        return {"repos": repos, "pr_count": pr_count,
                "issue_count": issue_count, "username": GITHUB_USERNAME}
    except Exception:
        return {"repos": [], "pr_count": "--", "issue_count": "--", "username": GITHUB_USERNAME}


def claude_billing_countdown():
    now = datetime.now()
    day = CLAUDE_BILLING_DAY
    nxt = now.replace(day=day, hour=0, minute=0, second=0, microsecond=0)
    if nxt <= now:
        m = now.month % 12 + 1
        y = now.year + (1 if now.month == 12 else 0)
        nxt = nxt.replace(year=y, month=m)
    d = nxt - now
    return f"{d.days}d {d.seconds // 3600}h"


# ── HTML helpers ─────────────────────────────────────────────────────────────
def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")


def synced_ago(iso):
    if not iso:
        return "never"
    try:
        dt = datetime.fromisoformat(iso)
        mins = int((datetime.now() - dt).total_seconds() / 60)
        if mins < 60:
            return f"{mins}m ago"
        return f"{mins // 60}h ago"
    except Exception:
        return "unknown"


CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:Georgia,serif; background:#fff; color:#000; font-size:20px;
       -webkit-user-select:none; user-select:none; }
#wrap { padding:20px 26px 80px 26px; max-width:1072px; margin:0 auto; }
.hdr { font-size:13px; letter-spacing:2px; text-transform:uppercase; color:#888;
       border-bottom:1px solid #000; padding-bottom:10px; margin-bottom:16px; }
.hdr .r { float:right; }
.tab { display:none; }
.tab.on { display:block; }

/* bottom bar */
#curtab { position:fixed; left:0; right:80px; bottom:0; height:70px; background:#000;
          color:#888; font-size:13px; letter-spacing:2px; text-transform:uppercase;
          line-height:70px; padding-left:22px; }
#mbtn { position:fixed; right:0; bottom:0; width:80px; height:70px; background:#111;
        color:#fff; font-size:32px; line-height:70px; text-align:center; cursor:pointer;
        border-left:1px solid #333; }
#menu { display:none; position:fixed; left:0; right:0; bottom:70px;
        background:#fff; border-top:3px solid #000; z-index:200; }
.mitem { display:block; padding:20px 26px; font-size:22px;
         border-bottom:1px solid #ddd; cursor:pointer; }
.mitem.mon { font-weight:bold; background:#f8f8f8; }

/* weather */
.hero { border-bottom:3px double #000; padding-bottom:16px; margin-bottom:16px; }
.temp { font-size:120px; font-weight:bold; line-height:0.85; letter-spacing:-4px;
        display:inline-block; vertical-align:top; }
.wright { display:inline-block; vertical-align:top; margin-left:22px; margin-top:10px; }
.cond { font-size:30px; font-style:italic; }
.wsub { font-size:18px; color:#555; margin-top:8px; }
.hilo { font-size:22px; margin-top:10px; }
.hilo b { font-size:26px; }
.wgrid { width:100%; border-collapse:collapse; margin:0 0 20px; }
.wgrid td { border:1px solid #ccc; padding:12px 10px; width:25%; }
.wlabel { font-size:11px; text-transform:uppercase; letter-spacing:1px; color:#999; }
.wval { font-size:22px; font-weight:bold; margin-top:4px; }
.ttab { width:100%; border-collapse:collapse; }
.ttab td { text-align:center; padding:8px 2px; }
.ttab .tval { font-size:20px; font-weight:bold; }
.ttab .thr { font-size:13px; color:#999; }
.rainh { font-size:13px; text-transform:uppercase; letter-spacing:2px; color:#888;
         border-bottom:2px solid #000; padding-bottom:5px; margin:0 0 12px; }

/* shared */
h2 { font-size:13px; text-transform:uppercase; letter-spacing:3px; border-bottom:2px solid #000;
     padding-bottom:5px; margin:24px 0 14px; }
h2:first-child { margin-top:0; }
.row { padding:14px 0; border-bottom:1px solid #ddd; }
.row .t { font-size:21px; font-weight:bold; }
.row .s { font-size:15px; color:#777; margin-top:3px; }
.empty { color:#aaa; font-style:italic; padding:14px 0; font-size:18px; }
.sync { font-size:13px; color:#bbb; margin-bottom:16px; }
.rate { font-size:28px; margin:12px 0; }
.rate b { font-size:32px; }

/* bot stats */
.sgrid { width:100%; border-collapse:collapse; margin-bottom:6px; }
.sgrid td { border:1px solid #ccc; padding:12px 10px; width:50%; vertical-align:top; }
.sl { font-size:11px; text-transform:uppercase; letter-spacing:1px; color:#999; }
.sv { font-size:36px; font-weight:bold; margin-top:4px; line-height:1; }
.full { width:100%; border-collapse:collapse; margin-bottom:6px; }
.full td { border:1px solid #ccc; padding:12px 10px; }
.inv { background:#000; color:#fff; }
.inv .sl { color:#aaa; }
.htab { width:100%; border-collapse:collapse; margin-top:4px; }
.htab th { font-size:11px; text-transform:uppercase; letter-spacing:1px; color:#999;
           text-align:left; padding:6px 8px; border-bottom:2px solid #000; }
.htab td { padding:10px 8px; border-bottom:1px solid #e2e2e2; font-size:19px; }
.htab .hh { font-weight:bold; }

/* claude */
.ctimer { font-size:96px; font-weight:bold; line-height:1; letter-spacing:-3px;
          text-align:center; padding:36px 0 8px; }
.csub { font-size:22px; color:#777; text-align:center; margin-bottom:32px; }
.cbar { width:100%; border-collapse:collapse; margin-bottom:24px; }
.cbar td { height:20px; }
.cmeta { font-size:18px; color:#555; text-align:center; line-height:1.9; }

/* news + save later */
.nitem { padding:18px 0; border-bottom:1px solid #ddd; }
.ntitle { font-size:22px; font-weight:bold; line-height:1.3; }
.nsrc { font-size:13px; color:#999; margin-top:4px; text-transform:uppercase; letter-spacing:1px; }
.nact { font-size:14px; color:#555; margin-top:8px; }
.nact span { border:1px solid #999; padding:4px 12px; margin-right:8px; cursor:pointer; }
.av { display:none; }
.backbtn { display:inline-block; background:#000; color:#fff; font-size:15px;
           padding:9px 18px; margin-bottom:18px; letter-spacing:1px; cursor:pointer; }
.atitle { font-size:26px; font-weight:bold; line-height:1.3; margin-bottom:12px; }
.asrc { font-size:13px; color:#999; margin-bottom:14px; text-transform:uppercase; letter-spacing:1px; }
.abody { font-size:20px; line-height:1.75; }
.abody p { margin:0 0 16px; }
.hnscore { font-size:13px; color:#999; margin-top:4px; }
.saved-empty { color:#aaa; font-style:italic; padding:20px 0; font-size:18px; }

/* github */
.repo { padding:12px 0; border-bottom:1px solid #ddd; }
.rname { font-size:20px; font-weight:bold; }
.rmeta { font-size:14px; color:#777; margin-top:3px; }
.lock { font-size:12px; border:1px solid #ccc; padding:1px 6px; color:#999; margin-left:6px; }

/* algo trader */
.pos { padding:14px 0; border-bottom:1px solid #ddd; }
.psym { font-size:22px; font-weight:bold; }
.pmeta { font-size:15px; color:#777; margin-top:4px; }
.pnl-pos { color:#000; font-weight:bold; }
.pnl-neg { color:#555; }

/* pharma pulse */
.pulse-item { padding:12px 0; border-bottom:1px solid #eee; }
.pulse-title { font-size:19px; line-height:1.3; }
.pulse-date { font-size:13px; color:#aaa; margin-top:3px; }
"""

JS_TEMPLATE = """
var _curtab='weather';
var _tabnames={weather:'Weather',bot:'Outreach Bot',day:'Day',
               claude:'Claude',news:'News',saved:'Saved',github:'GitHub',trader:'Trader'};

function show(id){
  var t=document.getElementsByClassName('tab');
  for(var i=0;i<t.length;i++) t[i].className='tab';
  document.getElementById('tab-'+id).className='tab on';
  _curtab=id;
  document.getElementById('curtab').innerHTML=_tabnames[id]||id;
  if(id==='saved') renderSaved();
  window.scrollTo(0,0);
}
function toggleMenu(){
  var m=document.getElementById('menu');
  if(m.style.display==='block'){
    m.style.display='none';
  } else {
    var items=m.getElementsByClassName('mitem');
    for(var i=0;i<items.length;i++){
      items[i].className='mitem'+(items[i].getAttribute('data-tab')===_curtab?' mon':'');
    }
    m.style.display='block';
  }
}
function goTab(id){ show(id); document.getElementById('menu').style.display='none'; }

function openArticle(n){
  document.getElementById('nl').style.display='none';
  var av=document.getElementsByClassName('av');
  for(var i=0;i<av.length;i++) av[i].style.display='none';
  document.getElementById('av-'+n).style.display='block';
  window.scrollTo(0,0);
}
function backToNews(){
  var av=document.getElementsByClassName('av');
  for(var i=0;i<av.length;i++) av[i].style.display='none';
  document.getElementById('nl').style.display='block';
  window.scrollTo(0,0);
}

/* Save Later */
function saveArticle(title, source, summary){
  var key='saved_'+Date.now();
  try{
    localStorage.setItem(key, JSON.stringify({title:title, source:source, body:summary,
                                              saved_at:new Date().toISOString()}));
    var btn=event.target; btn.innerHTML='Saved ✓'; btn.style.background='#000'; btn.style.color='#fff';
  } catch(e){ alert('Could not save: '+e); }
}
function deleteSaved(key){
  localStorage.removeItem(key);
  renderSaved();
}
function renderSaved(){
  var el=document.getElementById('saved-list');
  if(!el) return;
  var items=[];
  for(var i=0;i<localStorage.length;i++){
    var k=localStorage.key(i);
    if(k && k.indexOf('saved_')===0){
      try{ items.push({key:k, data:JSON.parse(localStorage.getItem(k))}); } catch(e){}
    }
  }
  items.sort(function(a,b){ return b.key>a.key?1:-1; });
  if(!items.length){
    el.innerHTML='<div class="saved-empty">No saved articles. Tap Read Later on any news item.</div>';
    return;
  }
  var html='';
  for(var j=0;j<items.length;j++){
    var it=items[j]; var d=it.data;
    html+='<div class="nitem">';
    html+='<div class="ntitle">'+esc(d.title||'')+'</div>';
    html+='<div class="nsrc">'+esc(d.source||'')+'</div>';
    if(d.body) html+='<div class="abody" style="margin-top:10px;font-size:18px">'+d.body.substring(0,400)+'&hellip;</div>';
    html+='<div class="nact"><span onclick="deleteSaved(\''+it.key+'\')">Remove</span></div>';
    html+='</div>';
  }
  el.innerHTML=html;
}
function esc(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

/* Claude session countdown */
var SESSION_TS=%d;
var SESSION_DUR=18000;
function updateClaude(){
  var now=Math.floor(Date.now()/1000);
  var elapsed=now-SESSION_TS;
  var rem=SESSION_DUR-elapsed;
  if(rem<0) rem=0;
  var h=Math.floor(rem/3600);
  var m=Math.floor((rem%%3600)/60);
  var el=document.getElementById('ctimer');
  if(el) el.innerHTML=h+'h '+(m<10?'0':'')+m+'m';
  var pct=Math.min(100,Math.round(elapsed/SESSION_DUR*100));
  var filled=Math.round(pct/5);
  var cells='';
  for(var i=0;i<20;i++)
    cells+='<td style="background:'+(i<filled?'#000':'#e0e0e0')+';height:20px"></td>';
  var bar=document.getElementById('cbar');
  if(bar) bar.innerHTML=cells;
  var rt=new Date((SESSION_TS+SESSION_DUR)*1000);
  var rh=rt.getHours(); var rm=rt.getMinutes();
  var ap=rh>=12?'PM':'AM'; rh=rh%%12||12;
  var rel=document.getElementById('creset');
  if(rel) rel.innerHTML='Resets at '+rh+':'+(rm<10?'0':'')+rm+' '+ap;
}
updateClaude();
setInterval(updateClaude,30000);
"""


# ── tab builders ─────────────────────────────────────────────────────────────
def weather_tab(w, aqi):
    rain_cells = "".join(
        '<td><div class="tval">%s%%</div><div class="thr">%s</div></td>' % (h["pop"], h["time"])
        for h in w["hours"])
    temp_cells = "".join(
        '<td><div class="tval">%s&deg;</div><div class="thr">%s</div></td>' % (h["temp"], h["time"])
        for h in w["hours"])
    return """
<div class="hero">
  <span class="temp">%s&deg;</span>
  <span class="wright">
    <div class="cond">%s</div>
    <div class="wsub">Mumbai &middot; feels %s&deg;</div>
    <div class="hilo">High <b>%s&deg;</b> &nbsp; Low <b>%s&deg;</b></div>
  </span>
</div>
<table class="wgrid"><tr>
  <td><div class="wlabel">Wind</div><div class="wval">%s km/h</div></td>
  <td><div class="wlabel">Humidity</div><div class="wval">%s%%</div></td>
  <td><div class="wlabel">UV</div><div class="wval">%s %s</div></td>
  <td><div class="wlabel">AQI</div><div class="wval">%s %s</div></td>
</tr></table>
<div class="rainh">Rain probability &mdash; next 8 hours</div>
<table class="ttab"><tr>%s</tr></table>
<div class="rainh" style="margin-top:20px">Temperature &mdash; next 8 hours</div>
<table class="ttab"><tr>%s</tr></table>
""" % (w["temp"], esc(w["condition"]), w["feels"], w["hi"], w["lo"],
       w["wind"], w["humidity"], w["uv"], w["uv_label"],
       aqi["aqi"], aqi["label"], rain_cells, temp_cells)


def bot_tab(private, forex):
    o = private.get("outreach", {})
    synced = synced_ago(private.get("synced_at"))
    if o.get("error"):
        stats_html = '<div class="empty">Outreach DB unavailable. Mac not synced.</div>'
    else:
        fu = o.get("followups_due", 0)
        fu_cls = ' class="inv"' if fu and fu != "--" and int(str(fu)) > 0 else ""
        ev_rows = "".join(
            '<tr><td class="hh">%s</td><td>%s</td><td>%s</td></tr>' % (
                esc(ev["date"]), esc(ev["type"]), esc(ev["company"]))
            for ev in o.get("events", []))
        events_html = ("""<h2>Recent Activity</h2>
<table class="htab">
  <tr><th>Date</th><th>Event</th><th>Company</th></tr>%s
</table>""" % ev_rows) if ev_rows else ""
        stats_html = """
<table class="sgrid">
  <tr>
    <td><div class="sl">Today Sent</div><div class="sv">%s</div></td>
    <td><div class="sl">In Pipeline</div><div class="sv">%s</div></td>
  </tr><tr>
    <td><div class="sl">Open Rate</div><div class="sv">%s%%</div></td>
    <td><div class="sl">Reply Rate</div><div class="sv">%s%%</div></td>
  </tr><tr>
    <td><div class="sl">Pending (NEW)</div><div class="sv">%s</div></td>
    <td><div class="sl">Email Opens</div><div class="sv">%s</div></td>
  </tr>
</table>
<table class="full">
  <tr%s><td><div class="sl">Follow-ups Due Today</div><div class="sv">%s</div></td></tr>
  <tr><td><div class="sl">Bounced</div><div class="sv">%s</div></td></tr>
</table>
%s""" % (o.get("today_sent","--"), o.get("in_pipeline","--"),
          o.get("open_rate","--"), o.get("reply_rate","--"),
          o.get("pending","--"), o.get("opens","--"),
          fu_cls, fu, o.get("bounced","--"), events_html)

    return """
<div class="sync">Mac synced: %s &nbsp;&bull;&nbsp; USD &#8377;%s &nbsp;&bull;&nbsp; EUR &#8377;%s</div>
<h2>Outreach Bot</h2>
%s
""" % (synced, forex["usd_inr"], forex["eur_inr"], stats_html)


def pharma_section(items):
    if not items:
        return '<div class="empty">No pharma/freight updates found.</div>'
    rows = "".join(
        '<div class="pulse-item"><div class="pulse-title">%s</div>'
        '<div class="pulse-date">%s</div></div>' % (esc(it["title"]), esc(it["date"]))
        for it in items)
    return rows


def day_tab(private):
    synced = synced_ago(private.get("synced_at"))
    events = private.get("calendar", [])
    reminders = private.get("reminders", [])
    notes = private.get("notes", [])

    ev_html = "".join(
        '<div class="row"><div class="t">%s</div><div class="s">%s</div></div>' % (
            esc(e["title"]), esc(e["time"]))
        for e in events) or '<div class="empty">No events today</div>'
    rm_html = "".join(
        '<div class="row"><div class="t">&#9633; %s</div></div>' % esc(r)
        for r in reminders) or '<div class="empty">No reminders</div>'
    note_html = ""
    if notes:
        note_html = "<h2>Notes</h2>" + "".join(
            '<div class="row"><div class="t">%s</div>'
            '<div class="s">%s</div></div>' % (esc(n["title"]), esc(n["preview"][:120]))
            for n in notes)

    return '<div class="sync">Mac synced: %s</div><h2>Calendar</h2>%s<h2>Reminders</h2>%s%s' % (
        synced, ev_html, rm_html, note_html)


def claude_tab(private, billing):
    ts = private.get("claude_session_ts", int(time.time()))
    synced = synced_ago(private.get("synced_at"))
    dt = datetime.fromtimestamp(ts)
    started = dt.strftime("%I:%M %p")
    return """
<div class="ctimer" id="ctimer">--</div>
<div class="csub">remaining in session</div>
<table class="cbar"><tr id="cbar"></tr></table>
<div class="cmeta">
  <div id="creset">&nbsp;</div>
  <div id="cstart">Started %s</div>
  <div style="margin-top:20px;font-size:16px;color:#aaa">Billing resets in <b>%s</b></div>
  <div style="font-size:13px;color:#bbb;margin-top:6px">Session from Mac sync: %s</div>
</div>
""" % (esc(started), esc(billing), synced)


def news_tab(articles, hn_stories, pharma_items):
    list_items = "".join(
        '<div class="nitem">'
        '<div class="ntitle" onclick="openArticle(%d)">%s</div>'
        '<div class="nsrc">%s</div>'
        '<div class="nact">'
        '<span onclick="openArticle(%d)">Read</span>'
        '<span onclick="saveArticle(\'%s\',\'%s\',\'%s\')">Read Later</span>'
        '</div></div>' % (
            i, esc(a["title"]), esc(a["source"]), i,
            esc(a["title"]).replace("'", "\\'"),
            esc(a["source"]).replace("'", "\\'"),
            esc(a["summary"]).replace("'", "\\'"))
        for i, a in enumerate(articles))

    article_views = "".join(
        '<div class="av" id="av-%d">'
        '<span class="backbtn" onclick="backToNews()">&lsaquo; News</span>'
        '<div class="asrc">%s</div>'
        '<div class="atitle">%s</div>'
        '<div class="abody"><p>%s</p></div>'
        '</div>' % (i, esc(a["source"]), esc(a["title"]), esc(a["summary"]))
        for i, a in enumerate(articles))

    hn_items = "".join(
        '<div class="nitem"><div class="ntitle">%s</div>'
        '<div class="hnscore">%s pts &middot; %s</div></div>' % (
            esc(s["title"]), s["score"], esc(s["by"]))
        for s in hn_stories)
    hn_section = ('<h2 style="margin-top:28px">Hacker News</h2>' + hn_items) if hn_items else ""

    pharma_html = ('<h2 style="margin-top:28px">Industry Pulse</h2>' + pharma_section(pharma_items))

    return '<div id="nl"><h2>News</h2>%s%s%s</div>%s' % (
        list_items, hn_section, pharma_html, article_views)


def saved_tab():
    return """
<h2>Saved Articles</h2>
<div id="saved-list"><div class="saved-empty">Loading&hellip;</div></div>
"""


def github_tab(gh):
    if not gh["username"] or gh["pr_count"] == "--":
        return '<div class="empty">Add GITHUB_TOKEN secret to GitHub Actions.</div>'
    stats = """
<table class="sgrid" style="margin-bottom:20px"><tr>
  <td><div class="sl">Open PRs</div><div class="sv">%s</div></td>
  <td><div class="sl">Open Issues</div><div class="sv">%s</div></td>
</tr></table>""" % (gh["pr_count"], gh["issue_count"])
    repos_html = "".join(
        '<div class="repo"><div class="rname">%s%s</div>'
        '<div class="rmeta">Pushed %s</div></div>' % (
            esc(r["name"]),
            '<span class="lock">private</span>' if r["private"] else "",
            esc(r["pushed"]))
        for r in gh["repos"]) or '<div class="empty">No repos found</div>'
    return '<h2>GitHub &mdash; %s</h2>%s<h2>Recent Repos</h2>%s' % (
        esc(gh["username"]), stats, repos_html)


def trader_tab(algo):
    if not algo:
        return '<div class="empty">No algo_data.json found. Run export_algo.py after main.py.</div>'
    synced = synced_ago(algo.get("synced_at", ""))
    positions = algo.get("positions", [])
    signals = algo.get("signals", [])
    pnl = algo.get("total_pnl", "--")
    pval = algo.get("portfolio_value", "--")
    status = algo.get("status", "unknown")

    pos_html = "".join(
        '<div class="pos">'
        '<div class="psym">%s <span style="font-size:16px;color:#999">%s</span></div>'
        '<div class="pmeta">Qty %s &nbsp;&bull;&nbsp; Avg &#8377;%s &nbsp;&bull;&nbsp; '
        'PnL <span class="%s">%s%%</span></div>'
        '</div>' % (
            esc(str(p.get("symbol",""))), esc(str(p.get("action",""))),
            p.get("qty","--"), p.get("avg_price","--"),
            "pnl-pos" if float(str(p.get("pnl_pct",0) or 0)) >= 0 else "pnl-neg",
            p.get("pnl_pct","--"))
        for p in positions[:8]) or '<div class="empty">No open positions</div>'

    sig_rows = "".join(
        '<tr><td class="hh">%s</td><td>%s</td><td>%s</td></tr>' % (
            esc(str(s.get("symbol",""))),
            esc(str(s.get("action",""))),
            esc(str(s.get("conviction",""))))
        for s in signals[:8])
    sig_html = ("""<h2>Latest Signals</h2>
<table class="htab">
  <tr><th>Symbol</th><th>Action</th><th>Conviction</th></tr>%s
</table>""" % sig_rows) if sig_rows else ""

    return """
<div class="sync">Synced: %s &nbsp;&bull;&nbsp; Status: %s</div>
<h2>Paper Portfolio</h2>
<table class="sgrid" style="margin-bottom:16px"><tr>
  <td><div class="sl">Portfolio Value</div><div class="sv" style="font-size:28px">&#8377;%s</div></td>
  <td><div class="sl">Total PnL</div><div class="sv" style="font-size:28px">&#8377;%s</div></td>
</tr></table>
<h2>Open Positions</h2>
%s
%s
""" % (synced, esc(status), esc(str(pval)), esc(str(pnl)), pos_html, sig_html)


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    print("Loading local data...")
    private = load_private_data()
    algo = load_algo_data()
    print(f"  private_data synced: {private.get('synced_at','never')}")
    print(f"  algo_data synced: {algo.get('synced_at','never')}")

    print("Fetching cloud data...")
    w     = fetch_weather();        print(f"  weather: {w['temp']}°C {w['condition']}")
    aqi   = fetch_aqi();            print(f"  AQI: {aqi['aqi']}")
    forex = fetch_currency();       print(f"  USD/INR: {forex['usd_inr']}")
    news  = fetch_news();           print(f"  news: {len(news)} articles")
    hn    = fetch_hn_top(5);        print(f"  HN: {len(hn)} stories")
    pharma= fetch_pharma_news();    print(f"  pharma news: {len(pharma)} items")
    gh    = fetch_github();         print(f"  github: {gh['username']}")
    billing = claude_billing_countdown()

    session_ts = private.get("claude_session_ts", int(time.time()))

    tabs = {
        "weather": weather_tab(w, aqi),
        "bot":     bot_tab(private, forex),
        "day":     day_tab(private),
        "claude":  claude_tab(private, billing),
        "news":    news_tab(news, hn, pharma),
        "saved":   saved_tab(),
        "github":  github_tab(gh),
        "trader":  trader_tab(algo),
    }
    tab_order  = ["weather","bot","day","claude","news","saved","github","trader"]
    tab_labels = {"weather":"Weather","bot":"Outreach Bot","day":"Day","claude":"Claude",
                  "news":"News","saved":"Saved","github":"GitHub","trader":"Trader"}

    tabs_divs = "".join(
        '<div id="tab-%s" class="%s">%s</div>\n' % (
            tid, "tab on" if tid == "weather" else "tab", tabs[tid])
        for tid in tab_order)

    menu_items = "".join(
        '<div class="mitem" data-tab="%s" onclick="goTab(\'%s\')">%s</div>' % (tid, tid, label)
        for tid, label in tab_labels.items())

    updated = datetime.now().strftime("%a %d %b %H:%M UTC")
    js = JS_TEMPLATE % session_ts

    html = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<meta http-equiv="refresh" content="3600">
<title>Dashboard</title>
<style>%s</style>
</head><body>
<div id="wrap">
<div class="hdr">Dashboard <span class="r">%s</span></div>
%s
</div>
<div id="curtab">Weather</div>
<div id="mbtn" onclick="toggleMenu()">&#9776;</div>
<div id="menu">%s</div>
<script>%s</script>
</body></html>""" % (CSS, updated, tabs_divs, menu_items, js)

    out = OUT_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"\nWritten {out} ({len(html)//1024}KB)")


if __name__ == "__main__":
    main()
