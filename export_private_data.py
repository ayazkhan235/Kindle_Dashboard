#!/usr/bin/env python3
"""Exports Mac-local data (outreach DB, calendar, notes) to private_data.json.
Run by SessionStart hook → git push → GitHub Actions picks it up."""
import json, os, subprocess, sqlite3, time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
OUT = BASE / "private_data.json"


def outreach_stats():
    db_path = os.path.expanduser("/Users/ayazkhan/outreach_bot/outreach.db")
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")

        def q(sql, params=()):
            c.execute(sql, params)
            return c.fetchone()[0]

        today_sent  = q("SELECT COUNT(*) FROM leads WHERE date(first_sent_at)=?", (today,))
        in_pipeline = q("SELECT COUNT(*) FROM leads WHERE status IN ('SENT','FOLLOW_UP_1','CONTACT_UPGRADED')")
        total_sent  = q("SELECT COUNT(*) FROM leads WHERE status NOT IN ('NEW','NOT_FOUND','WRONG_CONTACT')")
        replied     = q("SELECT COUNT(*) FROM leads WHERE reply_type IS NOT NULL AND reply_type != ''")
        pending     = q("SELECT COUNT(*) FROM leads WHERE status='NEW'")
        bounced     = q("SELECT COUNT(*) FROM leads WHERE status='BOUNCED'")
        opens       = q("SELECT COUNT(*) FROM opens")
        followups   = q("SELECT COUNT(*) FROM leads WHERE date(next_followup_at)=?", (today,))
        open_rate   = round(opens / max(total_sent, 1) * 100)
        reply_rate  = round(replied / max(total_sent, 1) * 100)

        c.execute("""SELECT e.created_at, e.event_type, l.company
                     FROM events e JOIN leads l ON e.email=l.email
                     ORDER BY e.created_at DESC LIMIT 5""")
        events = [{"date": (r[0] or "")[:10], "type": r[1], "company": r[2] or ""}
                  for r in c.fetchall()]
        conn.close()
        return {"today_sent": today_sent, "in_pipeline": in_pipeline,
                "total_sent": total_sent, "replied": replied, "pending": pending,
                "bounced": bounced, "opens": opens, "followups_due": followups,
                "open_rate": open_rate, "reply_rate": reply_rate, "events": events}
    except Exception as e:
        return {"error": str(e)}


def calendar_events():
    try:
        r = subprocess.run(
            ["icalBuddy", "-n", "-nrd", "-b", "• ", "-iep", "title,datetime",
             "-po", "title,datetime", "eventsToday"],
            capture_output=True, text=True, timeout=15)
        lines = [l.strip() for l in r.stdout.strip().splitlines() if l.strip()]
        events, cur = [], {}
        for line in lines:
            if line.startswith("•"):
                if cur: events.append(cur)
                cur = {"title": line[1:].strip(), "time": ""}
            elif cur:
                cur["time"] = line
        if cur: events.append(cur)
        return events[:8]
    except Exception:
        return []


def reminders():
    try:
        r = subprocess.run(["reminders", "show", "all"],
                           capture_output=True, text=True, timeout=10)
        return [l.strip().lstrip("•-* ") for l in r.stdout.strip().splitlines() if l.strip()][:10]
    except Exception:
        return []


def notes(n=3):
    try:
        script = (
            'tell application "Notes"\n'
            'set out to {}\n'
            'repeat with i from 1 to ' + str(n) + '\n'
            'try\n'
            'set nt to note i of default account\n'
            'set bd to plaintext of nt\n'
            'if length of bd > 300 then set bd to text 1 thru 300 of bd\n'
            'set out to out & {name of nt & "|||" & bd}\n'
            'end try\n'
            'end repeat\n'
            'return out\n'
            'end tell'
        )
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=10)
        result = []
        for item in r.stdout.strip().split(", "):
            if "|||" in item:
                title, preview = item.split("|||", 1)
                result.append({"title": title.strip(), "preview": preview.strip()})
        return result
    except Exception:
        return []


def claude_session_ts():
    try:
        return int(open(os.path.expanduser("~/.claude_session_start")).read().strip())
    except Exception:
        return int(time.time())


def main():
    print("Exporting private data...")
    data = {
        "synced_at": datetime.now().isoformat(),
        "outreach": outreach_stats(),
        "calendar": calendar_events(),
        "reminders": reminders(),
        "notes": notes(),
        "claude_session_ts": claude_session_ts(),
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Written {OUT}")

    # commit + push
    try:
        subprocess.run(["git", "-C", str(BASE), "add", "private_data.json"],
                       check=True, capture_output=True)
        result = subprocess.run(
            ["git", "-C", str(BASE), "diff", "--staged", "--quiet"],
            capture_output=True)
        if result.returncode != 0:
            subprocess.run(
                ["git", "-C", str(BASE), "commit", "-m",
                 f"private_data: {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
                check=True, capture_output=True)
            subprocess.run(["git", "-C", str(BASE), "push"],
                           check=True, capture_output=True)
            print("  Pushed to GitHub")
        else:
            print("  No changes to push")
    except Exception as e:
        print(f"  Git push failed: {e}")


if __name__ == "__main__":
    main()
