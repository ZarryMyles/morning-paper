#!/bin/sh
# Download today's paper from GitHub:
#   today.pdf -> documents/ (opens like a book; swipe to turn pages)
#   pages/*.png -> drawn pixel-for-pixel by the page viewer (viewer.sh)
#   public repo:  raw.githubusercontent.com (no login)
#   private repo: GitHub API with a read-only token from paper.local.conf
. /mnt/us/morningpaper/bin/common.sh

DOCS="/mnt/us/documents"
CACHE="$EXT_DIR/today.png"       # last good cover, kept for offline mornings
TMP="/tmp/morningpaper_dl"

is_png() { [ "$(dd if="$1" bs=1 skip=1 count=3 2>/dev/null)" = "PNG" ]; }
is_pdf() { [ "$(dd if="$1" bs=1 count=4 2>/dev/null)" = "%PDF" ]; }

# fetch_file NAME [DEST] -> downloads NAME from the paper branch (DEST defaults to $TMP)
fetch_file() {
    dest="${2:-$TMP}"
    rm -f "$dest"
    if [ -n "$GITHUB_TOKEN" ]; then
        url="https://api.github.com/repos/$GITHUB_REPO/contents/$1?ref=paper"
        if have curl; then
            curl -sSL --fail -m 120 -o "$dest" \
                -H "Authorization: Bearer $GITHUB_TOKEN" \
                -H "Accept: application/vnd.github.raw" \
                -H "User-Agent: morning-paper-kindle" "$url"
        else
            wget -q -T 120 -O "$dest" \
                --header="Authorization: Bearer $GITHUB_TOKEN" \
                --header="Accept: application/vnd.github.raw" \
                --header="User-Agent: morning-paper-kindle" "$url"
        fi
    else
        url="https://raw.githubusercontent.com/$GITHUB_REPO/paper/$1"
        if have curl; then curl -sSL --fail -m 120 -o "$dest" "$url"
        else wget -q -T 120 -O "$dest" "$url"; fi
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
    clear_screen
    draw_line 6 "Fetching today's paper..."

    # 1. Pages for the viewer: download into pages.new, swap in only if complete.
    total=""
    if fetch_file status.json; then
        total="$(sed -n 's/.*"pages": *\([0-9][0-9]*\).*/\1/p' "$TMP" | head -n 1)"
    fi
    pages_ok=0
    if [ "${total:-0}" -gt 0 ]; then
        rm -rf "$EXT_DIR/pages.new"; mkdir -p "$EXT_DIR/pages.new"
        i=1
        while [ "$i" -le "$total" ]; do
            f="$(printf 'page_%02d.png' "$i")"
            if ! fetch_file "pages/$f" || ! is_png "$TMP"; then
                break
            fi
            mv -f "$TMP" "$EXT_DIR/pages.new/$f"
            i=$((i + 1))
        done
        if [ "$i" -gt "$total" ]; then
            rm -rf "$EXT_DIR/pages"
            mv "$EXT_DIR/pages.new" "$EXT_DIR/pages"
            cp -f "$EXT_DIR/pages/page_01.png" "$CACHE"
            pages_ok=1
            log "fetch: $total pages downloaded"
        else
            rm -rf "$EXT_DIR/pages.new"
            log "fetch: page $i of $total FAILED; keeping the last complete edition"
        fi
    else
        log "fetch: status.json download FAILED"
    fi

    # 2. The PDF backup, in the background while you read.
    save_pdf &

    if [ "$pages_ok" -eq 0 ]; then
        if [ -s "$EXT_DIR/pages/page_01.png" ]; then
            log "fetch: offline, opening the last edition"
        else
            clear_screen
            draw_line 4 "Could not download today's paper."
            draw_line 6 "Private repo? Add paper.local.conf"
            draw_line 8 "with GITHUB_TOKEN. See log.txt."
            return 1
        fi
    fi
    return 0
}

save_pdf() {
    pdf_tmp="/tmp/morningpaper_pdf"     # its own file: runs alongside the viewer
    if fetch_file today.pdf "$pdf_tmp" && is_pdf "$pdf_tmp"; then
        name="The Mahanth Times - $(date +%Y-%m-%d).pdf"
        for old in "$DOCS"/"The Mahanth Times - "*.pdf; do   # keep only today's
            [ -f "$old" ] && [ "$old" != "$DOCS/$name" ] && rm -f "$old"
        done
        mv -f "$pdf_tmp" "$DOCS/$name"
        log "fetch: saved $name ($(wc -c < "$DOCS/$name") bytes)"
        rescan_library
    else
        log "fetch: today.pdf download FAILED (library copy unchanged)"
    fi
}

# Detached so the library closes first. On success the viewer takes over the
# screen; on failure the message stays up for HOLD_SECONDS.
(
    sleep 2
    echo "fetch-$(sh -c 'echo $PPID')" > "$RUN_FILE"
    if fetch; then
        sh "$EXT_DIR/bin/viewer.sh" --now
    else
        sleep "$HOLD_SECONDS"
        restore_home
    fi
) >> "$LOG" 2>&1 &
