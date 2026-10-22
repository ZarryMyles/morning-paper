#!/bin/sh
# Shared helpers for the Morning Paper test extension.
# Kindle runs BusyBox ash, so this file sticks to plain POSIX sh.

EXT_DIR="/mnt/us/morningpaper"
LOG="$EXT_DIR/log.txt"
HOLD_SECONDS=30
# shellcheck disable=SC2034  # used by net_test.sh after sourcing
IMAGE_URL=""
# shellcheck disable=SC2034  # used by fetch.sh after sourcing
GITHUB_REPO=""
GITHUB_TOKEN=""
[ -f "$EXT_DIR/paper.conf" ] && . "$EXT_DIR/paper.conf"
[ -f "$EXT_DIR/paper.local.conf" ] && . "$EXT_DIR/paper.local.conf"
# Strip Windows line endings in case a config was edited in Notepad.
GITHUB_REPO="$(printf '%s' "$GITHUB_REPO" | tr -d '\r')"
GITHUB_TOKEN="$(printf '%s' "$GITHUB_TOKEN" | tr -d '\r')"
IMAGE_URL="$(printf '%s' "$IMAGE_URL" | tr -d '\r')"
HOLD_SECONDS="$(printf '%s' "$HOLD_SECONDS" | tr -d '\r')"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

# --- Find FBInk (nicer renderer) if a jailbreak package installed it ----
FBINK="$(command -v fbink 2>/dev/null)"
[ -z "$FBINK" ] && for p in /usr/bin/fbink /mnt/us/libkh/bin/fbink /mnt/us/usbnet/bin/fbink \
         /mnt/us/koreader/fbink /mnt/us/libkh/bin/fbink /var/local/mkk/fbink \
         /mnt/us/extensions/MRInstaller/bin/K5/fbink /mnt/us/documents/.sh_integration/fbink; do
    if [ -x "$p" ]; then FBINK="$p"; break; fi
done

have() { command -v "$1" >/dev/null 2>&1; }

# --- Screen size: prints WIDTHxHEIGHT --------------------------------------
screen_res() {
    w=""; h=""
    if have eips; then
        info="$(eips -i 2>/dev/null)"
        w="$(echo "$info" | awk '{for(i=1;i<NF;i++) if($i=="xres:"){print $(i+1); exit}}')"
        h="$(echo "$info" | awk '{for(i=1;i<NF;i++) if($i=="yres:"){print $(i+1); exit}}')"
    fi
    if [ -z "$w" ] || [ -z "$h" ]; then
        # Fallback, e.g. "U:1072x1448p-85"
        mode="$(head -n 1 /sys/class/graphics/fb0/modes 2>/dev/null)"
        dims="$(echo "$mode" | sed -n 's/.*:\([0-9]*\)x\([0-9]*\).*/\1 \2/p')"
        w="${dims% *}"; h="${dims#* }"
    fi
    echo "${w}x${h}"
}

# --- Drawing ------------------------------------------------------------------
clear_screen() {
    if [ -n "$FBINK" ]; then "$FBINK" -q -c -f; else eips -c; eips -c; fi
}

# draw_line ROW "text"   (ROW = text line number from the top)
draw_line() {
    if [ -n "$FBINK" ]; then
        "$FBINK" -q -m -S 3 -y "$1" "$2"
    else
        eips 2 "$(( $1 * 2 ))" "$2"
    fi
}

draw_image() {
    if [ -n "$FBINK" ]; then
        "$FBINK" -q -c -f -g file="$1"
    else
        eips -f -g "$1"
    fi
}

# Give the home screen back after a test.
restore_home() {
    lipc-set-prop com.lab126.appmgrd start app://com.lab126.booklet.home 2>/dev/null \
        || clear_screen
}

# Run a test in the background so KUAL can close its menu first,
# then hold the result on screen and restore the home screen.
run_test() {
    (
        sleep 2
        "$@"
        sleep "$HOLD_SECONDS"
        restore_home
    ) >> "$LOG" 2>&1 &
}
