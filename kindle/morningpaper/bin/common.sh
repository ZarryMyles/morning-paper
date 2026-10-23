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
WAKE_TIME="05:30"
AUTO_FETCH=1
TOUCH_DEV=""
GITHUB_REPO=""
GITHUB_TOKEN=""
[ -f "$EXT_DIR/paper.conf" ] && . "$EXT_DIR/paper.conf"
[ -f "$EXT_DIR/paper.local.conf" ] && . "$EXT_DIR/paper.local.conf"
# Strip Windows line endings in case a config was edited in Notepad.
for v in HOLD_SECONDS VIEWER_IDLE_SECONDS WAKE_TIME AUTO_FETCH TOUCH_DEV GITHUB_REPO GITHUB_TOKEN; do
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

# Date of the edition on the device (from the downloaded status.json), e.g. 2026-10-23
edition_date() {
    sed -n 's/.*"date": *"\([0-9-]*\)".*/\1/p' "$EXT_DIR/pages/status.json" 2>/dev/null | head -n 1
}

# Is the screen showing the sleep screen (or about to suspend)?
in_screensaver() {
    lipc-get-prop com.lab126.powerd status 2>/dev/null | grep -qE "Screen Saver|Ready"
}

# Draw today's front page full-screen (used as the sleep screen).
draw_cover() {
    img="$EXT_DIR/pages/page_01.png"
    [ -s "$img" ] || return 1
    if [ -n "$FBINK" ]; then "$FBINK" -q -f -g file="$img",halign=CENTER,valign=CENTER
    else eips -f -g "$img"; fi
}

# Numbers like "05" or "09" without the leading zero (sh reads 09 as bad octal).
num() { v="$(echo "$1" | sed 's/^0*//')"; echo "${v:-0}"; }
