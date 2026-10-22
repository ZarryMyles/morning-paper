#!/bin/sh
# Shared settings and helpers for The Myles Times on the Kindle.
# Kindle runs BusyBox ash, so this file sticks to plain POSIX sh.
# shellcheck disable=SC2034  # settings below are used by fetch.sh / viewer.sh

EXT_DIR="/mnt/us/morningpaper"
LOG="$EXT_DIR/log.txt"
RUN_FILE="/tmp/morningpaper.run"

# Defaults (paper.conf overrides; paper.local.conf holds the token, if any)
HOLD_SECONDS=30
VIEWER_IDLE_SECONDS=600
TOUCH_DEV=""
GITHUB_REPO=""
GITHUB_TOKEN=""
[ -f "$EXT_DIR/paper.conf" ] && . "$EXT_DIR/paper.conf"
[ -f "$EXT_DIR/paper.local.conf" ] && . "$EXT_DIR/paper.local.conf"
# Strip Windows line endings in case a config was edited in Notepad.
for v in HOLD_SECONDS VIEWER_IDLE_SECONDS TOUCH_DEV GITHUB_REPO GITHUB_TOKEN; do
    eval "$v=\"\$(printf '%s' \"\$$v\" | tr -d '\r')\""
done

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

have() { command -v "$1" >/dev/null 2>&1; }

# FBInk draws sharper and faster than the built-in eips.
FBINK="$(command -v fbink 2>/dev/null)"
[ -z "$FBINK" ] && for p in /mnt/us/libkh/bin/fbink /usr/bin/fbink /mnt/us/usbnet/bin/fbink \
         /mnt/us/koreader/fbink /var/local/mkk/fbink; do
    if [ -x "$p" ]; then FBINK="$p"; break; fi
done

clear_screen() {
    if [ -n "$FBINK" ]; then "$FBINK" -q -c -f; else eips -c; eips -c; fi
}

# draw_line ROW "text"   (ROW = text line number from the top)
draw_line() {
    if [ -n "$FBINK" ]; then "$FBINK" -q -m -S 3 -y "$1" "$2"
    else eips 2 "$(( $1 * 2 ))" "$2"; fi
}

# Give the Kindle's home screen back.
restore_home() {
    lipc-set-prop com.lab126.appmgrd start app://com.lab126.booklet.home 2>/dev/null \
        || clear_screen
}
