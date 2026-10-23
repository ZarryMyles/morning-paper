#!/bin/sh
# The paper viewer: draws each page pixel-for-pixel and turns pages on touch.
#
#   tap right side / swipe left   -> next page
#   tap left 30% / swipe right    -> previous page
#   tap on the last page          -> close
#   long-press anywhere           -> close
#   tap an index entry (page 1)   -> jump to that page (targets from links.txt)
# Safety: closes after VIEWER_IDLE_SECONDS without a touch, or when the power
# button is pressed. tapread holds the touchscreen while open; the kernel
# releases it automatically if anything here dies.
. /mnt/us/morningpaper/bin/common.sh

PAGES="$EXT_DIR/pages"
FIFO="/tmp/morningpaper.touch"
LOCK="/tmp/morningpaper.viewer"
TAPREAD="/tmp/morningpaper_tapread"
SLEEPING="/tmp/morningpaper.sleeping"     # set when the power button closed us

# Tap target under (x, y) on this page, from the edition's links.txt (permille coords).
link_at() {
    [ -f "$PAGES/links.txt" ] || return 1
    awk -v pg="$1" -v x="$2" -v y="$3" \
        '$1 == pg && x >= $2 && x <= $4 && y >= $3 && y <= $5 { print $6; exit }' "$PAGES/links.txt"
}

# Find the touchscreen (12th gen: "pt_mt" on event1).
find_touch() {
    [ -n "$TOUCH_DEV" ] && { echo "$TOUCH_DEV"; return; }
    awk '/^N: Name=/ { touch = ($0 ~ /pt_mt|[Tt]ouch|cyttsp|zforce|elan/) }
         /^H: Handlers=/ && touch { for (i = 1; i <= NF; i++) if ($i ~ /^event[0-9]+$/) { print "/dev/input/" $i; exit } }' \
        /proc/bus/input/devices 2>/dev/null | head -n 1
}

show_page() {
    img="$PAGES/$(printf 'page_%02d.png' "$1")"
    if [ -n "$FBINK" ]; then
        "$FBINK" -q -f -g file="$img",halign=CENTER,valign=CENTER
    else
        eips -f -g "$img"
    fi
}

cleanup() {
    [ -n "$TAP_PID" ] && kill "$TAP_PID" 2>/dev/null
    [ -n "$WATCH_PID" ] && kill "$WATCH_PID" 2>/dev/null
    rm -f "$FIFO" "$LOCK"
    lipc-set-prop com.lab126.powerd preventScreenSaver 0 2>/dev/null
    lipc-set-prop com.lab126.pillow disableEnablePillow enable 2>/dev/null
    log "viewer: closed ($1)"
    if [ -f "$SLEEPING" ]; then
        rm -f "$SLEEPING"        # going to sleep: leave the screen to the sleep-screen cover
    else
        restore_home
    fi
}

view() {
    total="$(ls "$PAGES"/page_*.png 2>/dev/null | wc -l | tr -d ' ')"
    if [ "${total:-0}" -eq 0 ]; then
        clear_screen; draw_line 4 "No paper downloaded yet."; draw_line 6 "Tap 'The Myles Times' while online."
        sleep 8; restore_home; return 1
    fi

    # One viewer at a time. ($$ is the parent's PID inside a subshell, so ask a
    # child shell for its parent: that's this subshell.)
    me="$(sh -c 'echo $PPID')"
    if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK")" 2>/dev/null; then
        log "viewer: already open"; return 0
    fi
    echo "$me" > "$LOCK"
    # Tell any pending test timers that a newer screen owns the display.
    echo "viewer-$me" > "$RUN_FILE"

    dev="$(find_touch)"; dev="${dev:-/dev/input/event1}"
    # /mnt/us is a FAT drive; run the helper from RAM where it can be executable.
    cp -f "$EXT_DIR/bin/tapread" "$TAPREAD" && chmod +x "$TAPREAD"

    lipc-set-prop com.lab126.powerd preventScreenSaver 1 2>/dev/null
    lipc-set-prop com.lab126.pillow disableEnablePillow disable 2>/dev/null

    page=1
    show_page "$page"
    log "viewer: open, $total pages, touch=$dev"

    rm -f "$FIFO"; mkfifo "$FIFO"
    "$TAPREAD" --idle "${VIEWER_IDLE_SECONDS:-600}" "$dev" > "$FIFO" 2>> "$LOG" &
    TAP_PID=$!
    # Power button pressed -> close, so the Kindle can sleep normally.
    rm -f "$SLEEPING"
    ( lipc-wait-event com.lab126.powerd goingToScreenSaver >/dev/null 2>&1 \
        && touch "$SLEEPING" && kill "$TAP_PID" 2>/dev/null ) &
    WATCH_PID=$!

    reason="touchscreen helper stopped"
    while IFS=' ' read -r kind a b _; do
        case "$kind" in
            ready) log "viewer: touchscreen claimed" ;;
            tap)
                target="$(link_at "$page" "$a" "$b")"
                if [ -n "$target" ] && [ "$target" -ge 1 ] && [ "$target" -le "$total" ]; then
                    page="$target"; show_page "$page"                    # index entry
                elif [ "$a" -lt 300 ]; then
                    [ "$page" -gt 1 ] && { page=$((page - 1)); show_page "$page"; }
                elif [ "$page" -lt "$total" ]; then
                    page=$((page + 1)); show_page "$page"
                else
                    reason="finished the paper"; break
                fi ;;
            swipe)
                case "$a" in
                    left)  if [ "$page" -lt "$total" ]; then page=$((page + 1)); show_page "$page"
                           else reason="finished the paper"; break; fi ;;
                    right) [ "$page" -gt 1 ] && { page=$((page - 1)); show_page "$page"; } ;;
                esac ;;
            hold) reason="long-press"; break ;;
            idle) reason="no touches for ${VIEWER_IDLE_SECONDS:-600}s"; break ;;
        esac
    done < "$FIFO"
    [ -f "$SLEEPING" ] && reason="power button"
    cleanup "$reason"
}

# fetch.sh runs us with --now (already detached). From the library, detach
# first so the library can close; everything logs to log.txt.
if [ "$1" = "--now" ]; then
    view >> "$LOG" 2>&1
else
    ( sleep 2; view ) >> "$LOG" 2>&1 &
fi
