#!/bin/bash
set -e

KINDLE_HOST="172.20.10.2"
KINDLE_PORT="2222"
KINDLE_USER="root"
LOCAL_DIR="$(dirname "$0")"
MESQUITE_PATH="/var/local/mesquite/com.ayaz.dashboard"
SSH_OPTS="-p $KINDLE_PORT -o StrictHostKeyChecking=no -o ConnectTimeout=8"

echo "Generating dashboard..."
cd "$LOCAL_DIR"
python3 dashboard_webview.py

echo "Pushing to Kindle..."
scp $SSH_OPTS \
    "$LOCAL_DIR/kindleapp/Dashboard/index.html" \
    "$KINDLE_USER@$KINDLE_HOST:$MESQUITE_PATH/"

echo "Reloading..."
ssh $SSH_OPTS "$KINDLE_USER@$KINDLE_HOST" \
    "pkill -9 mesquite 2>/dev/null; sleep 1; lipc-set-prop com.lab126.appmgrd start app://com.ayaz.dashboard" \
    2>/dev/null || true

echo "Done."
