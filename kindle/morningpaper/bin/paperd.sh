#!/bin/sh
# paperd: the morning daemon. Started by the library book; runs until reboot.
#
#  * Kindle goes to sleep      -> draws today's front page over the sleep screen
#  * Kindle about to suspend   -> sets the real-time-clock alarm for WAKE_TIME
#  * alarm wakes the Kindle    -> turns Wi-Fi on, downloads the new edition,
#                                 draws its front page, restores Wi-Fi, sleeps again
#  * edition not out yet       -> tries again every 20 minutes for 4 hours
#                                 (GitHub's scheduled runs are often late)
#
# While waiting it blocks on lipc-wait-event, so it uses no CPU.
. /mnt/us/morningpaper/bin/common.sh

PIDFILE="/tmp/morningpaper.paperd.pid"
TRIES="/tmp/morningpaper.tries"          # "YYYY-MM-DD COUNT": fetch attempts today
LASTTRY="/tmp/morningpaper.lasttry"      # epoch of the last attempt (throttle)
MAX_TRIES=13                             # WAKE_TIME, then every 20 min for 4 hours
RETRY_SECONDS=1200
WIFI_WAIT=60

now_s() { date +%s; }
today() { date +%Y-%m-%d; }

# Minutes since midnight, now and at WAKE_TIME
now_min() { echo $(( $(num "$(date +%H)") * 60 + $(num "$(date +%M)") )); }
wake_min() { echo $(( $(num "${WAKE_TIME%:*}") * 60 + $(num "${WAKE_TIME#*:}") )); }

tries_today() {
    set -- $(cat "$TRIES" 2>/dev/null)
    if [ "$1" = "$(today)" ]; then echo "${2:-0}"; else echo 0; fi
}

# Does today still need a paper, and is it time to try?
needs_paper() {
    [ "$(num "$AUTO_FETCH")" -eq 1 ] || return 1
    [ "$(edition_date)" = "$(today)" ] && return 1
    [ "$(now_min)" -ge "$(wake_min)" ] || return 1          # never before WAKE_TIME
    [ "$(tries_today)" -lt "$MAX_TRIES" ] || return 1
    return 0
}

# Seconds until the next thing worth waking for (retry soon, or tomorrow's WAKE_TIME).
next_wait() {
    if needs_paper; then
        last="$(cat "$LASTTRY" 2>/dev/null || echo 0)"
        left=$(( last + RETRY_SECONDS - $(now_s) ))
        [ "$left" -gt 60 ] && echo "$left" || echo 60
        return
    fi
    secs=$(( ( $(wake_min) - $(now_min) ) * 60 ))
    [ "$secs" -le 60 ] && secs=$(( secs + 86400 ))
    echo "$secs"
}

wifi_connected() { [ "$(lipc-get-prop com.lab126.wifid cmState 2>/dev/null)" = "CONNECTED" ]; }

morning_fetch() {
    last="$(cat "$LASTTRY" 2>/dev/null || echo 0)"
    [ $(( $(now_s) - last )) -ge 300 ] || return 0            # at most once per 5 minutes
    now_s > "$LASTTRY"
    echo "$(today) $(( $(tries_today) + 1 ))" > "$TRIES"
    log "paperd: fetching the morning edition (try $(tries_today) of $MAX_TRIES)"

    # Ask powerd for a little time before it suspends again.
    lipc-set-prop com.lab126.powerd deferSuspend 120 2>/dev/null

    wifi_was="$(lipc-get-prop com.lab126.cmd wirelessEnable 2>/dev/null)"
    [ "$wifi_was" = "0" ] && lipc-set-prop com.lab126.cmd wirelessEnable 1 2>/dev/null
    waited=0
    while ! wifi_connected && [ "$waited" -lt "$WIFI_WAIT" ]; do
        sleep 2; waited=$((waited + 2))
    done

    if wifi_connected; then
        sh "$EXT_DIR/bin/fetch.sh" --quiet
        if [ "$(edition_date)" = "$(today)" ]; then
            log "paperd: today's edition is in"
        else
            log "paperd: edition not out yet ($(edition_date)); will retry"
        fi
    else
        log "paperd: no Wi-Fi after ${WIFI_WAIT}s; will retry"
    fi
    [ "$wifi_was" = "0" ] && lipc-set-prop com.lab126.cmd wirelessEnable 0 2>/dev/null
    in_screensaver && draw_cover
}

run() {
    echo $$ > "$PIDFILE"
    log "paperd: started (wake time $WAKE_TIME, auto-fetch $AUTO_FETCH)"
    while :; do
        wait_s="$(next_wait)"
        ev="$(lipc-wait-event -s "$wait_s" com.lab126.powerd \
              goingToScreenSaver,readyToSuspend,wakeupFromSuspend,resuming 2>/dev/null)"
        case "$ev" in
            goingToScreenSaver*)
                # Let the stock sleep screen draw first, then put the paper over it.
                ( sleep 3; draw_cover && log "paperd: front page set as sleep screen" ) & ;;
            readyToSuspend*)
                s="$(next_wait)"
                lipc-set-prop -i com.lab126.powerd rtcWakeup "$s" 2>/dev/null \
                    && log "paperd: alarm set for ${s}s from now" ;;
            wakeupFromSuspend*|resuming*)
                needs_paper && morning_fetch ;;
            "")
                # Timed out while awake: wake time (or a retry) has come.
                needs_paper && morning_fetch ;;
        esac
    done
}

# Single instance: started from the library book on every tap.
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    exit 0
fi
run >> "$LOG" 2>&1
