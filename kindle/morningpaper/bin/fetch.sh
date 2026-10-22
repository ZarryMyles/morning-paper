#!/bin/sh
# Download today's paper from GitHub:
#   today.pdf -> documents/ (opens like a book; swipe to turn pages)
#   today.png -> the cover, shown on screen now
#   public repo:  raw.githubusercontent.com (no login)
#   private repo: GitHub API with a read-only token from paper.local.conf
. /mnt/us/morningpaper/bin/common.sh

DOCS="/mnt/us/documents"
CACHE="$EXT_DIR/today.png"       # last good cover, kept for offline mornings
TMP="/tmp/morningpaper_dl"

is_png() { [ "$(dd if="$1" bs=1 skip=1 count=3 2>/dev/null)" = "PNG" ]; }
is_pdf() { [ "$(dd if="$1" bs=1 count=4 2>/dev/null)" = "%PDF" ]; }

# fetch_file NAME -> downloads NAME from the paper branch into $TMP
fetch_file() {
    rm -f "$TMP"
    if [ -n "$GITHUB_TOKEN" ]; then
        url="https://api.github.com/repos/$GITHUB_REPO/contents/$1?ref=paper"
        if have curl; then
            curl -sSL --fail -m 120 -o "$TMP" \
                -H "Authorization: Bearer $GITHUB_TOKEN" \
                -H "Accept: application/vnd.github.raw" \
                -H "User-Agent: morning-paper-kindle" "$url"
        else
            wget -q -T 120 -O "$TMP" \
                --header="Authorization: Bearer $GITHUB_TOKEN" \
                --header="Accept: application/vnd.github.raw" \
                --header="User-Agent: morning-paper-kindle" "$url"
        fi
    else
        url="https://raw.githubusercontent.com/$GITHUB_REPO/paper/$1"
        if have curl; then curl -sSL --fail -m 120 -o "$TMP" "$url"
        else wget -q -T 120 -O "$TMP" "$url"; fi
    fi
}

# Ask the Kindle to re-index documents/ so the new paper shows up right away.
rescan_library() {
    lipc-set-prop com.lab126.scanner doFullScan 1 2>/dev/null \
        || log "fetch: library rescan request failed (paper appears after next scan)"
}

fetch() {
    if [ -z "$GITHUB_REPO" ]; then
        log "fetch: GITHUB_REPO is empty in paper.conf"
        clear_screen; draw_line 4 "Set GITHUB_REPO in paper.conf"; return 1
    fi
    mode="public"; [ -n "$GITHUB_TOKEN" ] && mode="private"
    log "fetch: $mode mode for $GITHUB_REPO"

    # 1. The full paper (PDF) into the library
    pdf_ok=0
    if fetch_file today.pdf && is_pdf "$TMP"; then
        name="The Mahanth Times - $(date +%Y-%m-%d).pdf"
        # Keep only today's edition in the library.
        for old in "$DOCS"/"The Mahanth Times - "*.pdf; do
            [ -f "$old" ] && [ "$old" != "$DOCS/$name" ] && rm -f "$old"
        done
        mv -f "$TMP" "$DOCS/$name"
        log "fetch: saved $name ($(wc -c < "$DOCS/$name") bytes)"
        rescan_library
        pdf_ok=1
    else
        log "fetch: today.pdf download FAILED"
    fi

    # 2. The cover, drawn now
    if fetch_file today.png && is_png "$TMP"; then
        mv -f "$TMP" "$CACHE"
        clear_screen
        draw_image "$CACHE"
    elif [ -s "$CACHE" ]; then
        clear_screen
        draw_image "$CACHE"
        draw_line 2 "(offline - showing last edition)"
    else
        clear_screen
        draw_line 4 "Could not download today's paper."
        draw_line 6 "Private repo? Add paper.local.conf"
        draw_line 8 "with GITHUB_TOKEN. See log.txt."
        return 1
    fi
    [ "$pdf_ok" -eq 1 ] && log "fetch: done - open 'The Mahanth Times' in your library"
    return 0
}

# The cover stays up longer than a test.
HOLD="$PAPER_HOLD_SECONDS" run_test fetch
