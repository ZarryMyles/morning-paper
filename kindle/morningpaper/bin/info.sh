#!/bin/sh
# Test 1: collect device facts into info.txt and show a summary on screen.
. /mnt/us/morningpaper/bin/common.sh

OUT="$EXT_DIR/info.txt"

device_info() {
    res="$(screen_res)"
    fw="$(cat /etc/prettyversion.txt 2>/dev/null | head -n 1)"
    model="$(head -c 6 /proc/usid 2>/dev/null)"   # serial prefix = model code
    wifi="$(lipc-get-prop com.lab126.wifid cmState 2>/dev/null)"
    tools=""
    for t in fbink eips curl wget lipc-get-prop python3 python; do
        if [ "$t" = fbink ]; then
            [ -n "$FBINK" ] && tools="$tools fbink($FBINK)"
        elif have "$t"; then
            tools="$tools $t"
        fi
    done
    scriptlets="$(ls /mnt/us/documents/*.sh 2>/dev/null | wc -l)"
    fbink_found="$(find /usr /var/local /mnt/us -name fbink -type f 2>/dev/null | head -n 3 | tr '\n' ' ')"
    space="$(df -h /mnt/us 2>/dev/null | awk 'NR==2 {print $4 " free"}')"

    {
        echo "Morning Paper device info - $(date)"
        echo "screen:     $res"
        echo "firmware:   ${fw:-unknown}"
        echo "model code: ${model:-unknown}"
        echo "wifi:       ${wifi:-unknown}"
        echo "tools:     $tools"
        echo "scriptlets: $scriptlets in documents/"
        echo "fbink seen: ${fbink_found:-none}"
        echo "storage:    ${space:-unknown}"
    } > "$OUT"
    log "info: written to $OUT"

    clear_screen
    draw_line 3 "MORNING PAPER - DEVICE INFO"
    draw_line 6 "Screen:  $res"
    draw_line 8 "Model:   ${model:-unknown}"
    draw_line 10 "Wi-Fi:   ${wifi:-unknown}"
    draw_line 12 "FBInk:   ${FBINK:-not found (using eips)}"
    draw_line 15 "Full details saved to info.txt"
    draw_line 17 "in the morningpaper folder"
}

run_test device_info
