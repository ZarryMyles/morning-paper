#!/bin/sh
# Touch probe: gathers what's needed to build a tap-to-turn page viewer.
# Read-only and non-blocking: it only listens to the touchscreen, never grabs it.
. /mnt/us/morningpaper/bin/common.sh

OUT="$EXT_DIR/probe.txt"
RAW="$EXT_DIR/probe_raw"

probe() {
    mkdir -p "$RAW"
    clear_screen
    draw_line 4 "TOUCH PROBE"
    draw_line 7 "Tap the screen a few times:"
    draw_line 9 "left edge, right edge, middle."
    draw_line 12 "Recording for 10 seconds..."

    # Listen to every input device at once (plain reads, nothing is blocked).
    pids=""
    for dev in /dev/input/event*; do
        [ -e "$dev" ] || continue
        cat "$dev" > "$RAW/$(basename "$dev").bin" 2>/dev/null &
        pids="$pids $!"
    done
    sleep 10
    for p in $pids; do kill "$p" 2>/dev/null; done

    {
        echo "Morning Paper touch probe - $(date)"
        echo "== screen: $(screen_res)"
        echo "== uname: $(uname -a)"
        echo "== input devices"
        cat /proc/bus/input/devices 2>/dev/null
        echo "== captured bytes per device"
        for f in "$RAW"/*.bin; do [ -f "$f" ] && echo "$(basename "$f"): $(wc -c < "$f")"; done
        echo "== tools"
        for t in od hexdump xxd evtest timeout dd awk python3 lua luajit; do
            printf '%s: %s\n' "$t" "$(command -v "$t" 2>/dev/null || echo no)"
        done
        echo "== GUI processes"
        ps -o pid,comm 2>/dev/null | grep -iE "cvm|awesome|kpp|pillow|blanket|framework|xorg|webreader" \
            || ps | grep -iE "cvm|awesome|kpp|pillow|blanket|framework|xorg|webreader" | grep -v grep
        echo "== init jobs"
        initctl list 2>/dev/null | grep -iE "framework|lab126_gui|x " | head -n 20
        echo "== first touch bytes (hex)"
        for f in "$RAW"/*.bin; do
            [ -s "$f" ] || continue
            echo "-- $(basename "$f")"
            od -A d -t x1 "$f" 2>/dev/null | head -n 12
        done
    } > "$OUT" 2>&1
    log "probe: results in $OUT"

    clear_screen
    draw_line 4 "Touch probe done."
    draw_line 7 "Send morningpaper/probe.txt"
    draw_line 9 "to Claude."
}

run_test probe
