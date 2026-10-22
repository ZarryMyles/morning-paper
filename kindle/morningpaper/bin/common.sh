#!/bin/sh
# Shared helpers for the Morning Paper test extension.
# Kindle runs BusyBox ash, so this file sticks to plain POSIX sh.

EXT_DIR="/mnt/us/morningpaper"
LOG="$EXT_DIR/log.txt"
HOLD_SECONDS=30
PAPER_HOLD_SECONDS=1800
VIEWER_IDLE_SECONDS=600
TOUCH_DEV=""
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
PAPER_HOLD_SECONDS="$(printf '%s' "$PAPER_HOLD_SECONDS" | tr -d '\r')"
VIEWER_IDLE_SECONDS="$(printf '%s' "$VIEWER_IDLE_SECONDS" | tr -d '\r')"
TOUCH_DEV="$(printf '%s' "$TOUCH_DEV" | tr -d '\r')"

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
        "$FBINK" -q -c -f -g file="$1",halign=CENTER,valign=CENTER
    else
        eips -f -g "$1"
    fi
}

# Give the home screen back after a test.
restore_home() {
    lipc-set-prop com.lab126.appmgrd start app://com.lab126.booklet.home 2>/dev/null \
        || clear_screen
}

# Run a test in the background so the library can close first, then hold the
# result on screen and restore the home screen. HOLD overrides HOLD_SECONDS.
#
# "Last one wins": each run stamps its ID into RUN_FILE. When a hold ends, the
# home screen is restored only if no newer run has started since; otherwise an
# old test's timer would wipe whatever is on screen now (e.g. the paper).
RUN_FILE="/tmp/morningpaper.run"
run_test() {
    hold="${HOLD:-$HOLD_SECONDS}"
    run_id="$$-$(date +%s)"
    echo "$run_id" > "$RUN_FILE"
    (
        sleep 2
        "$@"
        log "drawn; holding ${hold}s (run $run_id)"
        sleep "$hold"
        if [ "$(cat "$RUN_FILE" 2>/dev/null)" = "$run_id" ]; then
            log "hold over; restoring home screen (run $run_id)"
            restore_home
        else
            log "hold over; a newer screen is up, leaving it (run $run_id)"
        fi
    ) >> "$LOG" 2>&1 &
}
