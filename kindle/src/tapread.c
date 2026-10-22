/*
 * tapread - claim a Kindle touchscreen and report gestures, one per line.
 *
 *   tapread [--nograb] [--idle SECONDS] /dev/input/event1
 *
 * Output (flushed immediately so a shell loop can react):
 *   ready             touchscreen claimed, waiting for input
 *   tap X Y           X, Y in permille of the screen (0-1000)
 *   swipe left|right|up|down
 *   hold X Y          finger held still for 0.8 s or more
 *   idle              no touches for --idle seconds; exits with status 3
 *
 * While running it holds an input "grab" (EVIOCGRAB), so the Kindle's own UI
 * underneath receives no touches. The kernel drops the grab automatically
 * when this process exits for ANY reason (even kill -9), so the touchscreen
 * can never be left stuck.
 *
 * Build (static, any ARMv7 Kindle):
 *   python -m ziglang cc -target arm-linux-musleabihf -static -Os -s \
 *       -o tapread tapread.c
 */
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/select.h>
#include <unistd.h>

/* The kernel's 32-bit ARM input_event: 16 bytes. Defined here on purpose:
 * libc headers built with 64-bit time_t would make struct timeval 16 bytes
 * and silently misread every event. */
struct ev32 {
    uint32_t sec, usec;
    uint16_t type, code;
    int32_t value;
};

#define HOLD_MS      800
#define SWIPE_PM     120   /* a swipe must travel 12% of the screen */
#define STILL_PM      50   /* a tap/hold moves less than 5% */

static int fd = -1, grabbed = 0;

static void release(void) {
    if (fd >= 0 && grabbed) ioctl(fd, EVIOCGRAB, 0);
}

static void on_signal(int sig) {
    (void)sig;
    release();
    _exit(0);
}

/* Gesture timing uses the events' own timestamps: exact, and replayable. */
static long ev_ms(const struct ev32 *e) {
    return (long)(e->sec % 1000000u) * 1000L + e->usec / 1000;
}

static int axis_max(int code, int fallback) {
    struct input_absinfo ai;
    if (fd >= 0 && ioctl(fd, EVIOCGABS(code), &ai) == 0 && ai.maximum > ai.minimum)
        return ai.maximum;
    return fallback;
}

static void say(const char *fmt, int a, int b) {
    printf(fmt, a, b);
    fflush(stdout);
}

int main(int argc, char **argv) {
    const char *dev = NULL;
    int nograb = 0, idle_s = 0;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--nograb")) nograb = 1;
        else if (!strcmp(argv[i], "--idle") && i + 1 < argc) idle_s = atoi(argv[++i]);
        else dev = argv[i];
    }
    if (!dev) {
        fprintf(stderr, "usage: tapread [--nograb] [--idle SECONDS] /dev/input/eventN\n");
        return 2;
    }

    fd = open(dev, O_RDONLY);
    if (fd < 0) {
        fprintf(stderr, "tapread: open %s: %s\n", dev, strerror(errno));
        return 1;
    }
    if (!nograb) {
        if (ioctl(fd, EVIOCGRAB, 1) == 0) grabbed = 1;
        else fprintf(stderr, "tapread: grab failed: %s (continuing)\n", strerror(errno));
    }
    signal(SIGTERM, on_signal);
    signal(SIGINT, on_signal);
    signal(SIGHUP, on_signal);
    atexit(release);

    int xmax = axis_max(ABS_MT_POSITION_X, 1272);
    int ymax = axis_max(ABS_MT_POSITION_Y, 1696);
    printf("ready\n");
    fflush(stdout);

    int slot = 0, down = 0, released = 0, have_start = 0;
    int x = -1, y = -1, sx = 0, sy = 0;
    long t_down = 0;
    struct ev32 ev;

    for (;;) {
        if (idle_s > 0) {
            fd_set rf;
            FD_ZERO(&rf);
            FD_SET(fd, &rf);
            struct timeval tv = {idle_s, 0};
            int r = select(fd + 1, &rf, NULL, NULL, &tv);
            if (r == 0) {
                printf("idle\n");
                fflush(stdout);
                return 3;
            }
            if (r < 0) {
                if (errno == EINTR) continue;
                return 1;
            }
        }
        ssize_t n = read(fd, &ev, sizeof ev);
        if (n == 0) return 0;                     /* end of a recorded file */
        if (n != (ssize_t)sizeof ev) {
            if (n < 0 && errno == EINTR) continue;
            fprintf(stderr, "tapread: short read (%zd)\n", n);
            return 1;
        }

        if (ev.type == EV_ABS) {
            switch (ev.code) {
            case ABS_MT_SLOT: slot = ev.value; break;
            case ABS_MT_TRACKING_ID:
                if (slot != 0) break;            /* follow the first finger only */
                if (ev.value >= 0) { down = 1; released = 0; have_start = 0; t_down = ev_ms(&ev); }
                else if (down) released = 1;
                break;
            case ABS_MT_POSITION_X: if (slot == 0) x = ev.value; break;
            case ABS_MT_POSITION_Y: if (slot == 0) y = ev.value; break;
            }
        } else if (ev.type == EV_SYN && ev.code == SYN_REPORT) {
            if (down && !have_start && x >= 0 && y >= 0) { sx = x; sy = y; have_start = 1; }
            if (released && have_start) {
                int px = (int)(1000L * x / xmax), py = (int)(1000L * y / ymax);
                int dx = (int)(1000L * (x - sx) / xmax), dy = (int)(1000L * (y - sy) / ymax);
                int adx = abs(dx), ady = abs(dy);
                long held = ev_ms(&ev) - t_down;
                if (adx >= SWIPE_PM && adx >= ady) say(dx < 0 ? "swipe left\n" : "swipe right\n", 0, 0);
                else if (ady >= SWIPE_PM) say(dy < 0 ? "swipe up\n" : "swipe down\n", 0, 0);
                else if (adx < STILL_PM && ady < STILL_PM && held >= HOLD_MS) say("hold %d %d\n", px, py);
                else say("tap %d %d\n", px, py);
                down = released = have_start = 0;
            }
        }
    }
}
