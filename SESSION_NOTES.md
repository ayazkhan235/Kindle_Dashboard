# Kindle Dashboard — Quick Reference

## What It Is
Personal dashboard on jailbroken Kindle PW7 via Mesquite browser. Served from GitHub Pages, deployed via SSH.

## Key Files
| File | Purpose |
|------|---------|
| `generate_cloud.py` | Fetches live data, builds `docs/index.html` |
| `kindleapp/Dashboard/index.html` | Copy of generated HTML — this is what gets SSH-deployed |
| `kindleapp/Dashboard/config.xml` | Mesquite manifest (gestures, chrome) |
| `export_private_data.py` | Exports Mac data → `private_data.json` |

## Tabs (bottom nav bar)
Wthr · Bot · Day · Claude · News · Saved · Git

- **Weather** — temp, AQI, rain/temp forecast
- **Bot** — USD/INR + EUR/INR rates, outreach stats, Industry Pulse news
- **Day** — calendar, reminders, notes
- **Claude** — session countdown, billing reset, AI/Claude news
- **News** — BBC/Reuters world news + Hacker News
- **Saved** — localStorage read-later articles
- **GitHub** — repos, PRs

## Deploy Commands
```bash
python3 generate_cloud.py
cp docs/index.html kindleapp/Dashboard/index.html
scp -P 2222 docs/index.html root@192.168.0.108:/var/local/mesquite/com.ayaz.dashboard/index.html
ssh -p 2222 root@192.168.0.108 "lipc-set-prop com.lab126.appmgrd stop app://com.ayaz.dashboard; sleep 1; lipc-set-prop com.lab126.appmgrd start app://com.ayaz.dashboard"
```

## Framebuffer Screenshot
```bash
ssh -p 2222 root@192.168.0.108 "dd if=/dev/fb0 bs=1088 count=1448 2>/dev/null" | python3 -c "
import sys; from PIL import Image
data=sys.stdin.buffer.read()
rows=[data[r*1088:r*1088+1072] for r in range(1448)]
Image.frombytes('L',(1072,1448),b''.join(rows)).save('/tmp/kindle.png')
"
```
Stride=1088, visible=1072×1448, 8bpp grayscale.

## X Button
System chrome — cannot remove. Appears on all KUAL-launched apps.
