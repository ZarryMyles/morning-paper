#!/bin/sh
# Test 2: draw the lines of message.txt on the screen.
. /mnt/us/morningpaper/bin/common.sh

show_text() {
    log "show_text: start (fbink=${FBINK:-none})"
    clear_screen
    row=6
    draw_line 3 "MORNING PAPER - TEXT TEST"
    while IFS= read -r line || [ -n "$line" ]; do
        line="$(echo "$line" | tr -d '\r')"
        draw_line "$row" "$line"
        row=$(( row + 2 ))
    done < "$EXT_DIR/message.txt"
    draw_line $(( row + 2 )) "(home screen returns in ${HOLD_SECONDS}s)"
    log "show_text: done"
}

run_test show_text
