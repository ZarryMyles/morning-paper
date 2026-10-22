#!/bin/sh
# Test 4: can this Kindle download over HTTP and HTTPS?
# Old firmware ships an old SSL library, so HTTPS may fail even when Wi-Fi works.
. /mnt/us/morningpaper/bin/common.sh

OUT="$EXT_DIR/net.txt"
TMP="/tmp/morningpaper_net"
HTTP_URL="http://example.com/"
HTTPS_URL="https://raw.githubusercontent.com/pascalw/kindle-dash/main/README.md"

# try NAME COMMAND...  -> prints "NAME: OK" or "NAME: FAIL (exit N)"
try() {
    name="$1"; shift
    rm -f "$TMP"
    "$@" > /dev/null 2>&1
    code=$?
    if [ "$code" -eq 0 ] && [ -s "$TMP" ]; then echo "$name: OK"
    else echo "$name: FAIL (exit $code)"; fi
}

is_png() { [ "$(dd if="$1" bs=1 skip=1 count=3 2>/dev/null)" = "PNG" ]; }

net_test() {
    wifi="$(lipc-get-prop com.lab126.wifid cmState 2>/dev/null)"
    {
        echo "Morning Paper network test - $(date)"
        echo "wifi: ${wifi:-unknown}"
        if have curl; then
            try "curl http " curl -s -m 20 -o "$TMP" "$HTTP_URL"
            try "curl https" curl -s -m 20 -o "$TMP" "$HTTPS_URL"
            # -k skips certificate checks: tells us if the failure is old certs vs old TLS
            try "curl https (no cert check)" curl -s -k -m 20 -o "$TMP" "$HTTPS_URL"
        else
            echo "curl: not installed"
        fi
        if have wget; then
            try "wget http " wget -q -T 20 -O "$TMP" "$HTTP_URL"
            try "wget https" wget -q -T 20 -O "$TMP" "$HTTPS_URL"
        else
            echo "wget: not installed"
        fi
    } > "$OUT"
    log "net_test: results in $OUT"

    clear_screen
    draw_line 3 "MORNING PAPER - NETWORK TEST"
    row=6
    while IFS= read -r line; do
        draw_line "$row" "$line"
        row=$(( row + 2 ))
    done < "$OUT"

    # Optional: download and show an image from paper.conf's IMAGE_URL
    if [ -n "$IMAGE_URL" ]; then
        img="/tmp/morningpaper_test.png"
        rm -f "$img"
        if have curl; then curl -s -k -m 30 -o "$img" "$IMAGE_URL"
        else wget -q -T 30 -O "$img" "$IMAGE_URL"; fi
        if [ -s "$img" ] && is_png "$img"; then
            log "net_test: downloaded $IMAGE_URL"
            sleep 6   # let you read the results first
            clear_screen
            draw_image "$img"
            echo "image download: OK ($IMAGE_URL)" >> "$OUT"
        else
            draw_line $(( row + 2 )) "IMAGE_URL download FAILED"
            echo "image download: FAIL ($IMAGE_URL)" >> "$OUT"
        fi
    fi
}

run_test net_test
