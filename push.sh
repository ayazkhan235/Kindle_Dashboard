#!/bin/bash
set -e

KINDLE_HOST="192.168.0.108"
KINDLE_PORT="2222"
KINDLE_USER="root"
KINDLE_PATH="/mnt/us/documents"
LOCAL_DIR="$(dirname "$0")"

echo "Pushing dashboard to Kindle..."

scp -P "$KINDLE_PORT" -o StrictHostKeyChecking=no \
    "$LOCAL_DIR/dashboard.html" \
    "$KINDLE_USER@$KINDLE_HOST:$KINDLE_PATH/"

ssh -p "$KINDLE_PORT" -o StrictHostKeyChecking=no \
    "$KINDLE_USER@$KINDLE_HOST" "mkdir -p $KINDLE_PATH/news"

scp -P "$KINDLE_PORT" -o StrictHostKeyChecking=no \
    "$LOCAL_DIR/news/"*.html \
    "$KINDLE_USER@$KINDLE_HOST:$KINDLE_PATH/news/"

echo "Done."
