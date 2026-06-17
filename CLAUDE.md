# Project Rules for Claude

## Files
- NEVER commit `docs/index.html` — GitHub Actions regenerates it hourly. Committing it locally causes merge conflicts every push.
- Only commit `generate_cloud.py` and `kindleapp/Dashboard/index.html` when making dashboard changes.
- Copy `docs/index.html` → `kindleapp/Dashboard/index.html` after running generator, but do not `git add docs/index.html`.

## Reading Code
- NEVER read full large files. Use `grep -n "pattern" file` to find the exact line first, then `Read` with `offset` + `limit` for just that section.
- `generate_cloud.py` is 900 lines. `docs/index.html` is 25KB. Never read these fully.
- Read `kindleapp/Dashboard/index.html` for HTML edits (it's the same as docs/index.html but tracked).

## Git Workflow
Always run before committing:
```bash
git pull --rebase
```
If conflict in `docs/index.html`, run `git checkout --theirs docs/index.html && git add docs/index.html` then continue.

## Kindle Deploy
```bash
python3 generate_cloud.py
cp docs/index.html kindleapp/Dashboard/index.html
scp -P 2222 docs/index.html root@192.168.0.108:/var/local/mesquite/com.ayaz.dashboard/index.html
ssh -p 2222 root@192.168.0.108 "lipc-set-prop com.lab126.appmgrd stop app://com.ayaz.dashboard; sleep 1; lipc-set-prop com.lab126.appmgrd start app://com.ayaz.dashboard"
```

## Key Facts
- Kindle IP: 192.168.0.108, SSH port 2222
- App live dir: `/var/local/mesquite/com.ayaz.dashboard/`
- Tabs: Weather, Bot, Day, Claude, News, Saved, GitHub (bottom nav bar)
- Nav is fixed bottom bar — no hamburger menu
