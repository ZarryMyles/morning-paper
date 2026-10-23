#!/bin/sh
# Download today's edition from GitHub, then open the viewer.
#   fetch.sh           from the library: show progress, then open the viewer
#   fetch.sh --quiet   from the morning daemon: download only, draw nothing
#   today.pdf -> documents/ (opens like a book; swipe to turn pages)
#   pages/*.png -> drawn pixel-for-pixel by the page viewer (viewer.sh)
#   public repo:  raw.githubusercontent.com (no login)
#   private repo: GitHub API with a read-only token from paper.local.conf
. /mnt/us/morningpaper/bin/common.sh

DOCS="/mnt/us/documents"
CACHE="$EXT_DIR/today.png"       # last good cover, kept for offline mornings
TMP="/tmp/morningpaper_dl"

QUIET=""; [ "$1" = "--quiet" ] && QUIET=1
say() { [ -n "$QUIET" ] || draw_line "$@"; }
cls() { [ -n "$QUIET" ] || clear_screen; }

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
        cls; say 4 "Set GITHUB_REPO in paper.conf"; return 1
    fi
    mode="public"; [ -n "$GITHUB_TOKEN" ] && mode="private"
    log "fetch: $mode mode for $GITHUB_REPO"
    cls
    say 6 "Fetching today's paper..."

    # 1. Pages for the viewer: download into pages.new, swap in only if complete.
    total=""
    rm -rf "$EXT_DIR/pages.new"; mkdir -p "$EXT_DIR/pages.new"
    if fetch_file status.json "$EXT_DIR/pages.new/status.json"; then
        total="$(sed -n 's/.*"pages": *\([0-9][0-9]*\).*/\1/p' "$EXT_DIR/pages.new/status.json" | head -n 1)"
    fi
    pages_ok=0
    if [ "${total:-0}" -gt 0 ]; then
        # Tap targets (index -> page). Optional: older editions don't have them.
        fetch_file links.txt "$EXT_DIR/pages.new/links.txt" || rm -f "$EXT_DIR/pages.new/links.txt"
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
        rm -rf "$EXT_DIR/pages.new"
        log "fetch: status.json download FAILED"
    fi

    # 2. The PDF backup: in the background while you read; skipped by the
    #    morning daemon to keep its wake-up short (the next library tap saves it).
    [ -z "$QUIET" ] && save_pdf &

    if [ "$pages_ok" -eq 0 ]; then
        if [ -s "$EXT_DIR/pages/page_01.png" ]; then
            log "fetch: offline, using the last edition"
        else
            cls
            say 4 "Could not download today's paper."
            say 6 "Private repo? Add paper.local.conf"
            say 8 "with GITHUB_TOKEN. See log.txt."
            return 1
        fi
    fi
    return 0
}

save_pdf() {
    pdf_tmp="/tmp/morningpaper_pdf"     # its own file: runs alongside the viewer
    if fetch_file today.pdf "$pdf_tmp" && is_pdf "$pdf_tmp"; then
        name="The Myles Times - $(date +%Y-%m-%d).pdf"
        # Keep only today's edition (also clears editions from before the rename).
        for old in "$DOCS"/"The Myles Times - "*.pdf "$DOCS"/"The Mahanth Times - "*.pdf; do
            [ -f "$old" ] && [ "$old" != "$DOCS/$name" ] && rm -f "$old"
        done
        mv -f "$pdf_tmp" "$DOCS/$name"
        log "fetch: saved $name ($(wc -c < "$DOCS/$name") bytes)"
        rescan_library
    else
        log "fetch: today.pdf download FAILED (library copy unchanged)"
    fi
}

# Morning daemon: download in the foreground and report success.
if [ -n "$QUIET" ]; then
    fetch >> "$LOG" 2>&1
    exit $?
fi

# From the library: detached so the library closes first. On success the viewer
# takes over the screen; on failure the message stays up for HOLD_SECONDS.
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
