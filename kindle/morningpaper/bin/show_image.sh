#!/bin/sh
# Test 3: draw the front page PNG that matches this screen.
. /mnt/us/morningpaper/bin/common.sh

show_image() {
    res="$(screen_res)"
    w="${res%x*}"; h="${res#*x}"
    img="$EXT_DIR/images/test_${res}.png"
    # Some firmware reports the panel in landscape; try the swapped size.
    [ -f "$img" ] || img="$EXT_DIR/images/test_${h}x${w}.png"
    log "show_image: screen=$res image=$img"

    if [ -f "$img" ]; then
        clear_screen
        draw_image "$img" || log "show_image: draw failed"
    else
        clear_screen
        draw_line 4 "No test image for screen $res"
        draw_line 6 "Send this size to Claude."
        log "show_image: no matching image"
    fi
}

run_test show_image
