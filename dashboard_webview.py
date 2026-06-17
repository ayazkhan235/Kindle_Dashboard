#!/usr/bin/env python3
"""Generates mesquite (WebKit 531) dashboard for Kindle PW7.
ES5 only: no const/let, no fetch(), no flexbox, tables + inline-block.
Data baked in on Mac, static HTML pushed to Kindle."""
from datetime import datetime
from pathlib import Path
import requests, time, os
import dashboard as d
import config

OUT = Path(__file__).parent / "kindleapp" / "Dashboard" / "index.html"


def get_claude_session_ts():
    try:
        return int(open(os.path.expanduser("~/.claude_session_start")).read().strip())
    except Exception:
        return int(time.time())


def fetch_weather_rich():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": config.MUMBAI_LAT, "longitude": config.MUMBAI_LON,
        "current": "temperature_2m,apparent_temperature,weathercode,precipitation,"
                   "windspeed_10m,relativehumidity_2m,uv_index",
        "hourly": "temperature_2m,precipitation_probability,precipitation,weathercode",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,uv_index_max",
        "timezone": "Asia/Kolkata", "forecast_days": 2,
    }
    try:
        j = requests.get(url, params=params, timeout=10).json()
        cur, hr, dy = j["current"], j["hourly"], j["daily"]
        now_h = datetime.now().hour
        sl = slice(now_h, now_h + 16)
        hours = [{"time": t.split("T")[1][:5], "temp": round(temp),
                  "pop": pp, "mm": pr, "cond": d.weather_code_label(wc)}
                 for t, temp, pp, pr, wc in zip(
                     hr["time"][sl], hr["temperature_2m"][sl],
                     hr["precipitation_probability"][sl],
                     hr["precipitation"][sl], hr["weathercode"][sl])]
        uv = round(cur.get("uv_index", 0))
        return {"temp": round(cur["temperature_2m"]), "feels": round(cur["apparent_temperature"]),
                "condition": d.weather_code_label(cur["weathercode"]),
                "wind": round(cur["windspeed_10m"]), "humidity": cur.get("relativehumidity_2m", "--"),
                "uv": uv, "uv_label": d.uv_label(uv), "precip": cur.get("precipitation", 0),
                "hi": round(dy["temperature_2m_max"][0]), "lo": round(dy["temperature_2m_min"][0]),
                "rain_sum": dy["precipitation_sum"][0], "hours": hours,
                "rain_hours": [(h["time"], h["pop"]) for h in hours[:8]]}
    except Exception:
        return {"temp": "--", "feels": "--", "condition": "unavailable", "wind": "--",
                "humidity": "--", "uv": "--", "uv_label": "", "precip": 0,
                "hi": "--", "lo": "--", "rain_sum": 0, "hours": [], "rain_hours": []}


CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:Georgia,serif; background:#fff; color:#000; font-size:20px;
       -webkit-user-select:none; }
#wrap { padding:20px 26px 90px 26px; }
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
.mitem { display:block; padding:22px 26px; font-size:22px;
         border-bottom:1px solid #ddd; cursor:pointer; }
.mitem.mon { font-weight:bold; background:#f8f8f8; }

/* weather hero */
.hero { border-bottom:3px double #000; padding-bottom:18px; margin-bottom:18px; }
.temp { font-size:120px; font-weight:bold; line-height:0.85; letter-spacing:-4px;
        display:inline-block; vertical-align:top; }
.wright { display:inline-block; vertical-align:top; margin-left:22px; margin-top:10px; }
.cond { font-size:30px; font-style:italic; }
.wsub { font-size:18px; color:#555; margin-top:8px; }
.hilo { font-size:22px; margin-top:12px; }
.hilo b { font-size:26px; }
.taphint { float:right; font-size:14px; color:#999; font-style:italic; margin-top:18px; }
.wgrid { width:100%; border-collapse:collapse; margin:0 0 22px; }
.wgrid td { border:1px solid #ccc; padding:14px 12px; width:25%; }
.wlabel { font-size:11px; text-transform:uppercase; letter-spacing:1px; color:#999; }
.wval { font-size:24px; font-weight:bold; margin-top:4px; }
.ttab { width:100%; border-collapse:collapse; }
.ttab td { text-align:center; padding:8px 2px; }
.ttab .tval { font-size:22px; font-weight:bold; }
.rainh { font-size:13px; text-transform:uppercase; letter-spacing:2px; color:#888;
         border-bottom:2px solid #000; padding-bottom:5px; margin:0 0 14px; }
.raintbl { width:100%; border-collapse:collapse; }
.raintbl td { text-align:center; padding:6px 2px; vertical-align:bottom; }
.raintbl .pct { font-weight:bold; font-size:17px; }
.raintbl .hr { color:#999; font-size:13px; margin-top:5px; }
.colwrap { height:80px; position:relative; width:60%; margin:6px auto 0; }
.col { position:absolute; bottom:0; left:0; right:0; background:#000; }
.colbg { position:absolute; bottom:0; left:0; right:0; top:0; background:#eee; }
.htab { width:100%; border-collapse:collapse; margin-top:4px; }
.htab th { font-size:11px; text-transform:uppercase; letter-spacing:1px; color:#999;
           text-align:left; padding:6px 8px; border-bottom:2px solid #000; }
.htab td { padding:11px 8px; border-bottom:1px solid #e2e2e2; font-size:19px; }
.htab .hh { font-weight:bold; }
.htab .rp { font-weight:bold; }
.htab .rp0 { color:#bbb; font-weight:normal; }

/* shared */
h2 { font-size:13px; text-transform:uppercase; letter-spacing:3px; border-bottom:2px solid #000;
     padding-bottom:5px; margin:24px 0 14px; }
h2:first-child { margin-top:0; }
.backbtn { display:inline-block; background:#000; color:#fff; font-size:15px;
           padding:9px 18px; margin-bottom:18px; letter-spacing:1px; cursor:pointer; }
.row { padding:14px 0; border-bottom:1px solid #ddd; }
.row .t { font-size:21px; font-weight:bold; }
.row .s { font-size:15px; color:#777; margin-top:3px; }
.empty { color:#aaa; font-style:italic; padding:14px 0; font-size:18px; }
.rate { font-size:30px; margin:16px 0; }
.rate b { font-size:34px; }

/* bot stats grid */
.sgrid { width:100%; border-collapse:collapse; margin-bottom:6px; }
.sgrid td { border:1px solid #ccc; padding:14px 10px; width:50%; vertical-align:top; }
.sgrid .sl { font-size:11px; text-transform:uppercase; letter-spacing:1px; color:#999; }
.sgrid .sv { font-size:36px; font-weight:bold; margin-top:4px; line-height:1; }
.sgrid .sv.red { color:#000; background:#000; color:#fff; padding:2px 8px; }
.full { width:100%; border-collapse:collapse; margin-bottom:6px; }
.full td { border:1px solid #ccc; padding:14px 10px; }
.full .sl { font-size:11px; text-transform:uppercase; letter-spacing:1px; color:#999; }
.full .sv { font-size:36px; font-weight:bold; margin-top:4px; line-height:1; }

/* claude tab */
.ctimer { font-size:96px; font-weight:bold; line-height:1; letter-spacing:-3px;
          text-align:center; padding:40px 0 10px; }
.csub { font-size:22px; color:#777; text-align:center; margin-bottom:36px; }
.cbar { width:100%; border-collapse:collapse; margin-bottom:28px; }
.cbar td { height:20px; }
.cmeta { font-size:18px; color:#555; text-align:center; line-height:1.8; }

/* news tab */
.nitem { padding:18px 0; border-bottom:1px solid #ddd; cursor:pointer; }
.ntitle { font-size:22px; font-weight:bold; line-height:1.3; }
.nsrc { font-size:13px; color:#999; margin-top:5px; text-transform:uppercase;
        letter-spacing:1px; }
.av { display:none; }
.atitle { font-size:26px; font-weight:bold; line-height:1.3; margin-bottom:14px; }
.asrc { font-size:13px; color:#999; margin-bottom:16px; text-transform:uppercase;
        letter-spacing:1px; }
.abody { font-size:20px; line-height:1.75; }
.abody p { margin:0 0 16px; }
.hnscore { font-size:13px; color:#999; margin-top:4px; }
.hnurl { font-size:13px; color:#aaa; margin-top:4px; word-break:break-all; }

/* github */
.repo { padding:14px 0; border-bottom:1px solid #ddd; }
.rname { font-size:20px; font-weight:bold; }
.rmeta { font-size:14px; color:#777; margin-top:4px; }
.lock { font-size:12px; border:1px solid #ccc; padding:1px 6px; color:#999; margin-left:6px; }
"""


JS = """
var _curtab = 'weather';
var _tabnames = {weather:'Weather',bot:'Outreach Bot',day:'Day',
                 rates:'Rates',claude:'Claude',news:'News',github:'GitHub'};

function show(id){
  var t=document.getElementsByClassName('tab');
  for(var i=0;i<t.length;i++){ t[i].className='tab'; }
  document.getElementById('tab-'+id).className='tab on';
  _curtab = id;
  document.getElementById('curtab').innerHTML = _tabnames[id] || id;
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
function goTab(id){
  show(id);
  document.getElementById('menu').style.display='none';
}
function wdetail(on){
  document.getElementById('w-main').style.display=on?'none':'block';
  document.getElementById('w-detail').style.display=on?'block':'none';
  window.scrollTo(0,0);
}
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

/* Claude session countdown */
var SESSION_TS = %d;
var SESSION_DUR = 18000;
function updateClaude(){
  var now=Math.floor(Date.now()/1000);
  var elapsed=now-SESSION_TS;
  var rem=SESSION_DUR-elapsed;
  if(rem<0) rem=0;
  var h=Math.floor(rem/3600);
  var m=Math.floor((rem%%3600)/60);
  document.getElementById('ctimer').innerHTML=h+'h '+(m<10?'0':'')+m+'m';
  var pct=Math.min(100,Math.round(elapsed/SESSION_DUR*100));
  var filled=Math.round(pct/5);
  var cells='';
  for(var i=0;i<20;i++){
    cells+='<td style="background:'+(i<filled?'#000':'#e0e0e0')+';height:20px"></td>';
  }
  document.getElementById('cbar').innerHTML=cells;
  var rt=new Date((SESSION_TS+SESSION_DUR)*1000);
  var rh=rt.getHours(); var rm=rt.getMinutes();
  var ap=rh>=12?'PM':'AM'; rh=rh%%12||12;
  document.getElementById('creset').innerHTML='Resets at '+rh+':'+(rm<10?'0':'')+rm+' '+ap;
  var st=new Date(SESSION_TS*1000);
  var sh=st.getHours(); var sm=st.getMinutes();
  var sap=sh>=12?'PM':'AM'; sh=sh%%12||12;
  document.getElementById('cstart').innerHTML='Started '+sh+':'+(sm<10?'0':'')+sm+' '+sap;
}
updateClaude();
setInterval(updateClaude,30000);
"""


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def weather_tab(w, aqi):
    rain_cells = ""
    for t, pct in w["rain_hours"]:
        p = int(pct) if isinstance(pct, (int, float)) else 0
        rain_cells += ('<td><div class="pct">%s%%</div>'
                       '<div class="colwrap"><div class="colbg"></div>'
                       '<div class="col" style="height:%d%%"></div></div>'
                       '<div class="hr">%s</div></td>') % (pct, p, t)
    temp_cells = "".join(
        '<td><div class="tval">%s&deg;</div><div class="hr">%s</div></td>' % (h["temp"], h["time"])
        for h in w["hours"][:8])
    hrows = ""
    for h in w["hours"]:
        p = int(h["pop"]) if isinstance(h["pop"], (int, float)) else 0
        cls = "rp" if p >= 20 else "rp rp0"
        mm = ("%.1f mm" % h["mm"]) if h["mm"] else "&mdash;"
        hrows += ('<tr><td class="hh">%s</td><td>%s&deg;</td>'
                  '<td class="%s">%s%%</td><td>%s</td><td>%s</td></tr>') % (
            h["time"], h["temp"], cls, h["pop"], mm, esc(h["cond"]))
    return """
<div id="w-main">
 <div class="hero" onclick="wdetail(1)">
   <span class="taphint">tap for hourly &rsaquo;</span>
   <span class="temp">%s&deg;</span>
   <span class="wright"><div class="cond">%s</div>
     <div class="wsub">Mumbai &middot; feels %s&deg;</div>
     <div class="hilo">High <b>%s&deg;</b> &nbsp; Low <b>%s&deg;</b></div>
   </span>
 </div>
 <table class="wgrid">
  <tr><td><div class="wlabel">Wind</div><div class="wval">%s</div></td>
      <td><div class="wlabel">Humidity</div><div class="wval">%s%%</div></td>
      <td><div class="wlabel">UV</div><div class="wval">%s %s</div></td>
      <td><div class="wlabel">AQI</div><div class="wval">%s %s</div></td></tr>
 </table>
 <div class="rainh">Rain probability &mdash; next 8 hours</div>
 <table class="raintbl" onclick="wdetail(1)"><tr>%s</tr></table>
 <div class="rainh" style="margin-top:22px">Temperature &mdash; next 8 hours</div>
 <table class="ttab"><tr>%s</tr></table>
</div>
<div id="w-detail" style="display:none">
 <span class="backbtn" onclick="wdetail(0)">&lsaquo; Back</span>
 <div class="rainh">Hourly forecast &mdash; rain today %s mm</div>
 <table class="htab">
  <tr><th>Time</th><th>Temp</th><th>Rain</th><th>Amount</th><th>Sky</th></tr>
  %s
 </table>
</div>
""" % (w["temp"], esc(w["condition"]), w["feels"], w["hi"], w["lo"],
       str(w["wind"]) + " km/h", str(w["humidity"]),
       w["uv"], w["uv_label"], aqi["aqi"], aqi["label"],
       rain_cells, temp_cells, w["rain_sum"], hrows)


def bot_tab(o):
    followup_style = ' style="background:#000;color:#fff"' if o["followups_due"] and o["followups_due"] != "--" and int(str(o["followups_due"])) > 0 else ""
    events_rows = ""
    for ev in o.get("events", []):
        events_rows += '<tr><td class="hh">%s</td><td>%s</td><td>%s</td></tr>' % (
            esc(ev["date"]), esc(ev["type"]), esc(ev["company"]))
    events_section = ""
    if events_rows:
        events_section = """<h2>Recent Activity</h2>
<table class="htab">
  <tr><th>Date</th><th>Event</th><th>Company</th></tr>
  %s
</table>""" % events_rows

    return """
<h2>Outreach Bot</h2>
<table class="sgrid">
  <tr>
    <td><div class="sl">Today Sent</div><div class="sv">%s</div></td>
    <td><div class="sl">In Pipeline</div><div class="sv">%s</div></td>
  </tr>
  <tr>
    <td><div class="sl">Open Rate</div><div class="sv">%s%%</div></td>
    <td><div class="sl">Reply Rate</div><div class="sv">%s%%</div></td>
  </tr>
  <tr>
    <td><div class="sl">Pending (NEW)</div><div class="sv">%s</div></td>
    <td><div class="sl">Email Opens</div><div class="sv">%s</div></td>
  </tr>
</table>
<table class="full">
  <tr%s>
    <td><div class="sl">Follow-ups Due Today</div><div class="sv">%s</div></td>
  </tr>
  <tr>
    <td><div class="sl">Bounced</div><div class="sv">%s</div></td>
  </tr>
</table>
%s
""" % (o["today_sent"], o["in_pipeline"],
       o["open_rate"], o["reply_rate"],
       o["pending"], o["opens"],
       followup_style, o["followups_due"],
       o["bounced"], events_section)


def day_tab(events, reminders, notes):
    ev = "".join(
        '<div class="row"><div class="t">%s</div><div class="s">%s</div></div>' % (esc(e["title"]), esc(e["time"]))
        for e in events) or '<div class="empty">No events today</div>'
    rm = "".join(
        '<div class="row"><div class="t">&#9633; %s</div></div>' % esc(r)
        for r in reminders) or '<div class="empty">No reminders</div>'
    notes_html = ""
    if notes:
        note_rows = "".join(
            '<div class="row"><div class="t">%s</div><div class="s">%s</div></div>' % (
                esc(n["title"]), esc(n["preview"][:120]))
            for n in notes)
        notes_html = '<h2>Notes</h2>' + note_rows
    return '<h2>Calendar</h2>%s<h2>Reminders</h2>%s%s' % (ev, rm, notes_html)


def rates_tab(c, claude_billing):
    return """
<h2>Rates</h2>
<div class="rate">USD / INR &nbsp; <b>&#8377;%s</b></div>
<div class="rate">EUR / INR &nbsp; <b>&#8377;%s</b></div>
<div style="height:20px"></div>
<h2>Claude Billing</h2>
<div class="rate">Resets in <b>%s</b></div>
""" % (c["usd_inr"], c["eur_inr"], claude_billing)


def claude_tab(session_ts):
    dt = datetime.fromtimestamp(session_ts)
    started_str = dt.strftime("%I:%M %p")
    return """
<div class="ctimer" id="ctimer">--</div>
<div class="csub">remaining in session</div>
<table class="cbar"><tr id="cbar"></tr></table>
<div class="cmeta">
  <div id="creset">&nbsp;</div>
  <div id="cstart">Started %s</div>
</div>
""" % esc(started_str)


def news_tab(articles, hn_stories):
    list_items = ""
    for i, a in enumerate(articles):
        list_items += ('<div class="nitem" onclick="openArticle(%d)">'
                       '<div class="ntitle">%s</div>'
                       '<div class="nsrc">%s</div></div>') % (i, esc(a["title"]), esc(a["source"]))
    hn_items = ""
    if hn_stories:
        for s in hn_stories:
            hn_items += ('<div class="nitem">'
                         '<div class="ntitle">%s</div>'
                         '<div class="hnscore">%s pts &middot; %s</div></div>') % (
                esc(s["title"]), s["score"], esc(s["by"]))
    hn_section = ('<h2 style="margin-top:28px">Hacker News</h2>' + hn_items) if hn_items else ""

    article_views = ""
    for i, a in enumerate(articles):
        body = a.get("body") or ""
        content = body if len(body.strip()) > 60 else "<p>%s</p>" % esc(a.get("summary", ""))
        article_views += ('<div class="av" id="av-%d">'
                          '<span class="backbtn" onclick="backToNews()">&lsaquo; News</span>'
                          '<div class="asrc">%s</div>'
                          '<div class="atitle">%s</div>'
                          '<div class="abody">%s</div></div>') % (
            i, esc(a["source"]), esc(a["title"]), content)

    return '<div id="nl"><h2>News</h2>%s%s</div>%s' % (list_items, hn_section, article_views)


def github_tab(gh):
    if not gh["username"]:
        return '<div class="empty">Add GITHUB_TOKEN to config.py to enable.</div>'
    pr_val = str(gh["pr_count"])
    issue_val = str(gh["issue_count"])
    stats = """
<table class="sgrid" style="margin-bottom:22px">
  <tr>
    <td><div class="sl">Open PRs</div><div class="sv">%s</div></td>
    <td><div class="sl">Open Issues</div><div class="sv">%s</div></td>
  </tr>
</table>""" % (pr_val, issue_val)
    repos_html = ""
    for r in gh["repos"]:
        priv = '<span class="lock">private</span>' if r["private"] else ""
        repos_html += ('<div class="repo"><div class="rname">%s%s</div>'
                       '<div class="rmeta">Pushed %s</div></div>') % (
            esc(r["name"]), priv, esc(r["pushed"]))
    if not repos_html:
        repos_html = '<div class="empty">No repos found</div>'
    return '<h2>GitHub &mdash; %s</h2>%s<h2>Recent Repos</h2>%s' % (
        esc(gh["username"]), stats, repos_html)


def main():
    print("Fetching data...")
    w = fetch_weather_rich()
    print("  weather ok")
    aqi = d.fetch_aqi()
    print("  aqi ok")
    c = d.fetch_currency()
    print("  currency ok")
    events = d.fetch_calendar()
    print("  calendar: %d events" % len(events))
    reminders = d.fetch_reminders()
    print("  reminders: %d items" % len(reminders))
    notes = d.fetch_notes()
    print("  notes: %d items" % len(notes))
    o = d.fetch_outreach_db()
    print("  outreach db ok")
    claude_billing = d.claude_reset_countdown()
    session_ts = get_claude_session_ts()
    print("  claude session ts: %d" % session_ts)

    articles_raw = d.fetch_news()
    print("  news: %d articles, fetching bodies..." % len(articles_raw))
    articles = []
    for a in articles_raw:
        body = d.fetch_article_body(a["url"])
        articles.append({**a, "body": body or ""})
        print("    %s" % a["title"][:50])

    hn = d.fetch_hn_top(5)
    print("  HN: %d stories" % len(hn))

    gh = d.fetch_github()
    print("  github: %s" % (gh["username"] or "no token"))

    updated = datetime.now().strftime("%a %d %b %H:%M")

    tabs_html = {
        "weather": weather_tab(w, aqi),
        "bot": bot_tab(o),
        "day": day_tab(events, reminders, notes),
        "rates": rates_tab(c, claude_billing),
        "claude": claude_tab(session_ts),
        "news": news_tab(articles, hn),
        "github": github_tab(gh),
    }
    tab_order = ["weather", "bot", "day", "rates", "claude", "news", "github"]
    tab_labels = {"weather": "Weather", "bot": "Outreach Bot", "day": "Day",
                  "rates": "Rates", "claude": "Claude", "news": "News", "github": "GitHub"}

    tabs_divs = ""
    for tid in tab_order:
        cls = "tab on" if tid == "weather" else "tab"
        tabs_divs += '<div id="tab-%s" class="%s">%s</div>\n' % (tid, cls, tabs_html[tid])

    menu_items = "".join(
        '<div class="mitem" data-tab="%s" onclick="goTab(\'%s\')">%s</div>' % (tid, tid, label)
        for tid, label in tab_labels.items())

    html = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<style>%s</style></head>
<body>
<div id="wrap">
<div class="hdr">Dashboard <span class="r">%s</span></div>
%s
</div>
<div id="curtab">Weather</div>
<div id="mbtn" onclick="toggleMenu()">&#9776;</div>
<div id="menu">%s</div>
<script>%s</script>
</body></html>""" % (CSS, updated, tabs_divs, menu_items, JS % session_ts)

    OUT.write_text(html, encoding="utf-8")
    print("Wrote %s" % OUT)


if __name__ == "__main__":
    main()
