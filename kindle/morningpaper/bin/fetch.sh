#!/bin/sh
# Download today's paper from GitHub and draw it.
#   public repo:  raw.githubusercontent.com (no login)
#   private repo: GitHub API with a read-only token from paper.local.conf
. /mnt/us/morningpaper/bin/common.sh

CACHE="$EXT_DIR/today.png"      # last good edition, kept for offline mornings
TMP="/tmp/morningpaper_today.png"

is_png() { [ "$(dd if="$1" bs=1 skip=1 count=3 2>/dev/null)" = "PNG" ]; }

# Public download: no headers needed.
download_public() {
    rm -f "$TMP"
    if have curl; then curl -sSL --fail -m 60 -o "$TMP" "$1"
    else wget -q -T 60 -O "$TMP" "$1"; fi
}

# Private download via the GitHub API ("raw" media type returns the file bytes).
download_private() {
    rm -f "$TMP"
    if have curl; then
        curl -sSL --fail -m 60 -o "$TMP" \
            -H "Authorization: Bearer $GITHUB_TOKEN" \
            -H "Accept: application/vnd.github.raw" \
            -H "User-Agent: morning-paper-kindle" "$1"
    else
        wget -q -T 60 -O "$TMP" \
            --header="Authorization: Bearer $GITHUB_TOKEN" \
            --header="Accept: application/vnd.github.raw" \
            --header="User-Agent: morning-paper-kindle" "$1"
    fi
}

fetch() {
    if [ -z "$GITHUB_REPO" ]; then
        log "fetch: GITHUB_REPO is empty in paper.conf"
        clear_screen; draw_line 4 "Set GITHUB_REPO in paper.conf"; return 1
    fi

    if [ -n "$GITHUB_TOKEN" ]; then
        log "fetch: private mode (API) for $GITHUB_REPO"
        download_private "https://api.github.com/repos/$GITHUB_REPO/contents/today.png?ref=paper"
    else
        log "fetch: public mode (raw) for $GITHUB_REPO"
        download_public "https://raw.githubusercontent.com/$GITHUB_REPO/paper/today.png"
    fi
    code=$?

    if [ "$code" -eq 0 ] && [ -s "$TMP" ] && is_png "$TMP"; then
        mv -f "$TMP" "$CACHE"
        log "fetch: OK ($(wc -c < "$CACHE") bytes)"
        clear_screen
        draw_image "$CACHE"
        return 0
    fi

    log "fetch: FAILED (exit $code)"
    clear_screen
    if [ -s "$CACHE" ]; then
        draw_image "$CACHE"            # yesterday's paper beats a blank screen
        draw_line 2 "(offline - showing last edition)"
    else
        draw_line 4 "Could not download today's paper."
        draw_line 6 "Private repo? Add paper.local.conf"
        draw_line 8 "with GITHUB_TOKEN. See log.txt."
    fi
    return 1
}

# The paper stays up much longer than a test.
HOLD="$PAPER_HOLD_SECONDS" run_test fetch
