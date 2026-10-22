"""The Mahanth Times -- builds the full multi-page edition.

    python generator/paper.py --out out              # live data
    python generator/paper.py --out out --fixtures   # sample data, no network

Outputs: out/today.pdf (all pages), out/today.png (cover), out/pages/*.png,
out/status.json (which sources worked).
"""
import argparse
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"
IST = timezone(timedelta(hours=5, minutes=30))
FIRST_EDITION = datetime(2026, 10, 22, tzinfo=IST)
W, H = 1272, 1696                      # Paperwhite 12th gen framebuffer
BLACK, INK, SOFT, MID, LIGHT, FAINT, PAPER = 0, 30, 85, 120, 190, 225, 255


# ===== Typography ===============================================================
_cache = {}


def _font(file, size, weight=None):
    key = (file, size, weight)
    if key not in _cache:
        f = ImageFont.truetype(str(FONTS / file), size)
        if weight is not None:
            try:
                f.set_variation_by_axes([weight])
            except Exception:  # noqa: BLE001
                pass
        _cache[key] = f
    return _cache[key]


def serif(size, weight=500):
    return _font("Lora-Variable.ttf", size, weight)


def italic(size, weight=500):
    return _font("Lora-Italic-Variable.ttf", size, weight)


def sans(size):
    return _font("Inter-Regular.otf", size)


def sans_b(size):
    return _font("Inter-SemiBold.otf", size)


def display(size):
    return _font("DejaVuSerif-Bold.ttf", size)


class Page:
    """One 1272x1696 page plus layout helpers (sizes in px, designed at 1272)."""

    def __init__(self):
        self.img = Image.new("L", (W, H), PAPER)
        self.d = ImageDraw.Draw(self.img)
        self.m = 64                        # outer margin
        self.cw = W - 2 * self.m           # content width
        self.bottom = H - 110              # content must stay above the footer

    def tw(self, text, font):
        return self.d.textlength(text, font=font)

    def text(self, xy, text, font, fill=INK):
        self.d.text(xy, text, font=font, fill=fill)

    def wrap(self, text, font, width):
        lines, line = [], ""
        for word in (text or "").split():
            trial = f"{line} {word}".strip()
            if self.tw(trial, font) <= width or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines

    def para(self, x, y, text, font, width, lead, fill=INK, max_lines=None):
        lines = self.wrap(text, font, width)
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            last = lines[-1]
            while last and self.tw(last + "…", font) > width:
                last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
            lines[-1] = last + "…"
        for ln in lines:
            self.text((x, y), ln, font, fill)
            y += lead
        return y

    def para_height(self, text, font, width, lead, max_lines=None):
        n = len(self.wrap(text, font, width))
        return (min(n, max_lines) if max_lines else n) * lead

    def rule(self, y, weight=2, x0=None, x1=None, fill=BLACK):
        x0 = self.m if x0 is None else x0
        x1 = W - self.m if x1 is None else x1
        self.d.rectangle([x0, y, x1, y + weight - 1], fill=fill)

    def centered(self, y, text, font, fill=INK):
        self.text(((W - self.tw(text, font)) / 2, y), text, font, fill)

    def right(self, y, text, font, fill=INK, x1=None):
        x1 = W - self.m if x1 is None else x1
        self.text((x1 - self.tw(text, font), y), text, font, fill)


# ===== Shared page furniture ======================================================
def section_frame(p, now, kicker, title, deck=None):
    """Running header + section title. Returns the y where content starts."""
    y = 46
    p.text((p.m, y), "The Mahanth Times", serif(30, 700), BLACK)
    p.right(y + 8, now.strftime("%a %d %b %Y").upper(), sans_b(20))
    y += 52
    p.rule(y, 4)
    y += 34
    p.text((p.m, y), kicker.upper(), sans_b(22), SOFT)
    y += 36
    tf = serif(84, 700)
    while p.tw(title, tf) > p.cw and tf.size > 48:
        tf = serif(tf.size - 4, 700)
    p.text((p.m, y + (84 - tf.size) // 2), title, tf, BLACK)
    y += 108
    if deck:
        y = p.para(p.m, y, deck, italic(30), p.cw, 42, SOFT) + 6
    p.rule(y, 2)
    return y + 34


def footer(p, n, total):
    y = H - 84
    p.rule(y, 2)
    if n == total:
        p.centered(y + 22, "— That's today's paper. Tap once more to close. —", italic(26))
    elif n == 1:
        p.centered(y + 22, "Tap right for the next page  ·  tap left to go back  ·  press and hold to close",
                   sans(21), SOFT)
    else:
        p.centered(y + 22, f"— {n} of {total} —", sans(22), SOFT)


def unavailable(p, y, what):
    p.para(p.m, y + 40, f"{what} could not be fetched this morning. It will be back tomorrow.",
           italic(34), p.cw, 48, SOFT)


def fmt_int(n):
    return f"{n:,}"


# ===== Pages ======================================================================
def page_cover(p, now, data, contents):
    w, a = data.get("weather"), data.get("air")
    edition = (now.date() - FIRST_EDITION.date()).days + 1
    y = 50
    p.text((p.m, y), f"MORNING EDITION  ·  NO. {edition:03d}", sans_b(22))
    p.right(y, "PRICE: ZERO SCROLLS", sans_b(22))
    y += 46
    mast = serif(132, 700)
    title = "The Mahanth Times"
    if p.tw(title, mast) > p.cw:
        mast = serif(int(132 * p.cw / p.tw(title, mast)), 700)
    p.centered(y, title, mast, BLACK)
    y += mast.size + 30
    p.rule(y, 6)
    y += 16
    p.centered(y, now.strftime("%A, %d %B %Y").upper() + "  ·  THANISANDRA, BENGALURU", sans(24))
    y += 40
    p.rule(y, 2)
    y += 40

    # --- At a glance: weather | air -------------------------------------------
    box_h = 250
    half = (p.cw - 40) // 2
    from sources import WMO  # noqa: PLC0415
    x = p.m
    p.text((x, y), "WEATHER", sans_b(20), SOFT)
    if w:
        p.text((x, y + 30), f"{w['max']:.0f}°", serif(130, 600), BLACK)
        tx = x + p.tw(f"{w['max']:.0f}°", serif(130, 600)) + 24
        p.text((tx, y + 58), WMO.get(w["code"], "—"), serif(36, 650), BLACK)
        p.text((tx, y + 106), f"Low {w['min']:.0f}°  ·  Rain {w['rain']}%", sans(26))
        p.text((tx, y + 146), f"Sunrise {w['sunrise']}  ·  Sunset {w['sunset']}", sans(22), SOFT)
    else:
        p.text((x, y + 40), "Unavailable", italic(34), SOFT)
    x2 = p.m + half + 40
    p.d.rectangle([x2 - 21, y, x2 - 20, y + box_h - 30], fill=MID)
    p.text((x2, y), "AIR QUALITY", sans_b(20), SOFT)
    if a:
        p.text((x2, y + 30), f"{a['aqi']:.0f}", serif(130, 600), BLACK)
        tx = x2 + p.tw(f"{a['aqi']:.0f}", serif(130, 600)) + 24
        p.para(tx, y + 58, a["band"], serif(36, 650), W - p.m - tx, 44, BLACK, max_lines=2)
        p.text((tx, y + 150), "US AQI", sans(22), SOFT)
    else:
        p.text((x2, y + 40), "Unavailable", italic(34), SOFT)
    y += box_h
    p.rule(y, 2)
    y += 36

    # --- Lead story: first local headline ------------------------------------------
    news = data.get("news")
    lead = None
    if news:
        lead = news[0]["items"][0] | {"section": news[0]["name"]}
    if lead:
        p.text((p.m, y), f"TOP STORY  ·  {lead['section'].upper()}", sans_b(20), SOFT)
        y += 36
        y = p.para(p.m, y, lead["title"], display(54), p.cw, 66, BLACK, max_lines=3) + 10
        if lead.get("summary"):
            y = p.para(p.m, y, lead["summary"], italic(30), p.cw, 42, INK, max_lines=3)
        y += 30
        p.rule(y, 2)
        y += 36

    # --- Inside: table of contents -----------------------------------------------
    p.text((p.m, y), "INSIDE TODAY", sans_b(20), SOFT)
    y += 40
    row = 50
    fits = max(0, (p.bottom - y) // row)
    for title, page_no in contents[:fits]:
        f = serif(32, 560)
        num = str(page_no)
        p.text((p.m, y), title, f)
        nx = W - p.m - p.tw(num, f)
        dots_x0 = p.m + p.tw(title, f) + 16
        dx = dots_x0
        while dx < nx - 22:  # dotted leader
            p.d.ellipse([dx, y + 26, dx + 3, y + 29], fill=MID)
            dx += 14
        p.text((nx, y), num, f, BLACK)
        y += row


def page_weather(p, now, w):
    from sources import WMO  # noqa: PLC0415
    y = section_frame(p, now, "Weather · Thanisandra", "Today's Weather",
                      f"{WMO.get(w['code'], 'Mixed skies')} with a high of {w['max']:.0f}° "
                      f"and a {w['rain']}% chance of rain.")
    # Big hi/lo
    p.text((p.m, y - 10), f"{w['max']:.0f}°", serif(220, 600), BLACK)
    hx = p.m + p.tw(f"{w['max']:.0f}°", serif(220, 600)) + 20
    p.text((hx, y + 40), "HIGH", sans_b(20), SOFT)
    p.text((hx, y + 66), f"{w['max']:.1f}°C", sans(30))
    p.text((hx, y + 120), "LOW", sans_b(20), SOFT)
    p.text((hx, y + 146), f"{w['min']:.1f}°C", sans(30))
    # Stats grid on the right
    stats = [("Rain", f"{w['rain']}% · {w['rain_mm']:.1f} mm"), ("Humidity", f"{w['humidity']}%"),
             ("Wind", f"up to {w['wind_max']:.0f} km/h"), ("UV index", f"{w['uv']:.0f}"),
             ("Sunrise", w["sunrise"]), ("Sunset", w["sunset"])]
    gx = W // 2 + 40
    gy = y
    for i, (k, v) in enumerate(stats):
        cx, cy = gx + (i % 2) * 260, gy + (i // 2) * 84
        p.text((cx, cy), k.upper(), sans_b(18), SOFT)
        p.text((cx, cy + 26), v, sans(28), BLACK)
    y += 270

    # Tip line (advice that doesn't contradict itself on a stormy day)
    tips = []
    if w["rain"] >= 40:
        tips.append("carry an umbrella")
    if w["uv"] >= 7 and w["rain"] < 60:
        tips.append("sunscreen if you're out midday")
    if w["max"] >= 32:
        tips.append("stay hydrated")
    if not tips:
        tips.append("a good day to be outside")
    p.para(p.m, y, "Today: " + ", ".join(tips) + ".", serif(32, 600), p.cw, 44, BLACK)
    y += 70
    p.rule(y, 2)
    y += 30

    # Hourly: temperature line on top, rain chance in its own strip below,
    # so a 100%-rain day can't bury the temperature curve.
    p.text((p.m, y), "HOUR BY HOUR", sans_b(20), SOFT)
    y += 40
    hrs = w["hourly"]
    if hrs:
        cx0, cx1 = p.m + 70, W - p.m - 28   # room for the last rain bar
        ch = 200
        base = y + 30 + ch
        temps = [h["temp"] for h in hrs]
        lo, hi = min(temps) - 1, max(temps) + 1
        step = (cx1 - cx0) / max(1, len(hrs) - 1)
        for g in range(3):  # gridlines + temp labels
            gyy = base - g * ch / 2
            p.rule(int(gyy), 1, cx0, cx1, FAINT)
            p.text((p.m, gyy - 12), f"{lo + g * (hi - lo) / 2:.0f}°", sans(18), SOFT)
        pts = [(cx0 + i * step, base - (h["temp"] - lo) / (hi - lo) * ch) for i, h in enumerate(hrs)]
        p.d.line(pts, fill=BLACK, width=5, joint="curve")
        for i, (x, yy) in enumerate(pts):
            if hrs[i]["hour"] % 3 == 0:
                p.d.ellipse([x - 7, yy - 7, x + 7, yy + 7], fill=BLACK)
                lbl = f"{hrs[i]['temp']:.0f}°"
                p.text((x - p.tw(lbl, sans_b(20)) / 2, yy - 36), lbl, sans_b(20), BLACK)

        # Rain strip
        ry0 = base + 26
        rh = 80
        p.text((p.m, ry0 + rh / 2 - 12), "Rain", sans_b(18), SOFT)
        bw = step * 0.6
        for i, h in enumerate(hrs):
            x = cx0 + i * step
            r = h["rain"] or 0
            p.d.rectangle([x - bw / 2, ry0, x + bw / 2, ry0 + rh], outline=FAINT)
            if r:
                p.d.rectangle([x - bw / 2, ry0 + rh * (1 - r / 100), x + bw / 2, ry0 + rh], fill=MID)
            if h["hour"] % 3 == 0:
                rl = f"{r}%"
                p.text((x - p.tw(rl, sans(17)) / 2, ry0 + rh + 8), rl, sans(17), INK)
                hl = f"{h['hour']:02d}:00"
                p.text((x - p.tw(hl, sans(18)) / 2, ry0 + rh + 34), hl, sans(18), SOFT)
        y = ry0 + rh + 76
    p.rule(y, 2)
    y += 30

    # Outlook
    p.text((p.m, y), "THE NEXT THREE DAYS", sans_b(20), SOFT)
    y += 44
    days = w["days"][1:4]
    colw = p.cw / max(1, len(days))
    for i, dday in enumerate(days):
        x = p.m + i * colw
        dt = datetime.strptime(dday["date"], "%Y-%m-%d")
        p.text((x, y), dt.strftime("%A"), serif(34, 650), BLACK)
        p.text((x, y + 48), f"{dday['max']:.0f}° / {dday['min']:.0f}°", sans(30))
        p.para(x, y + 92, WMO.get(dday["code"], "—"), sans(22), colw - 20, 30, SOFT, max_lines=2)
        p.text((x, y + 156), f"Rain {dday['rain']}%", sans(22), SOFT)
        if i:
            p.d.rectangle([x - 20, y, x - 19, y + 180], fill=FAINT)


def page_air(p, now, a):
    from sources import AQI_BANDS  # noqa: PLC0415
    y = section_frame(p, now, "Air quality · Thanisandra", "The Air Today", a["advice"])
    p.text((p.m, y - 16), f"{a['aqi']:.0f}", serif(240, 600), BLACK)
    bx = p.m + p.tw(f"{a['aqi']:.0f}", serif(240, 600)) + 30
    p.text((bx, y + 50), "US AQI", sans_b(22), SOFT)
    p.para(bx, y + 84, a["band"], serif(54, 700), W - p.m - bx, 62, BLACK, max_lines=2)
    y += 300

    # Gauge: bands shaded light->dark, marker at the reading
    p.text((p.m, y), "WHERE TODAY SITS", sans_b(20), SOFT)
    y += 40
    edges = [0, 50, 100, 150, 200, 300, 400]
    shades = [235, 205, 170, 130, 90, 50]
    gx0, gx1, gh = p.m, W - p.m, 54
    span = gx1 - gx0
    pos = lambda v: gx0 + span * min(v, 400) / 400  # noqa: E731
    for i in range(6):
        p.d.rectangle([pos(edges[i]), y, pos(edges[i + 1]) - 3, y + gh], fill=shades[i])
        lbl = str(edges[i])
        p.text((pos(edges[i]) + 4, y + gh + 10), lbl, sans(18), SOFT)
    mx = pos(a["aqi"])
    p.d.polygon([(mx - 16, y - 20), (mx + 16, y - 20), (mx, y + 2)], fill=BLACK)
    p.d.rectangle([mx - 2, y, mx + 2, y + gh], fill=BLACK)
    y += gh + 44
    names = [b[1] for b in AQI_BANDS]
    p.para(p.m, y, "  ·  ".join(f"{e}–{edges[i + 1]} {names[i]}" for i, e in enumerate(edges[:-2])),
           sans(18), p.cw, 26, SOFT)
    y += 70
    p.rule(y, 2)
    y += 30

    # Pollutants
    p.text((p.m, y), "WHAT'S IN THE AIR (µg/m³)", sans_b(20), SOFT)
    y += 44
    pol = [("PM2.5", a["pm2_5"], "fine particles"), ("PM10", a["pm10"], "dust, pollen"),
           ("O₃", a["o3"], "ozone"), ("NO₂", a["no2"], "traffic exhaust"), ("CO", a["co"], "carbon monoxide")]
    colw = p.cw / 5
    for i, (name, val, what) in enumerate(pol):
        x = p.m + i * colw
        p.text((x, y), name, sans_b(26), BLACK)
        p.text((x, y + 38), "—" if val is None else f"{val:.0f}", serif(56, 600), BLACK)
        p.text((x, y + 110), what, sans(18), SOFT)
    y += 170
    p.rule(y, 2)
    y += 30

    # Hourly AQI bars
    p.text((p.m, y), "AQI THROUGH THE DAY", sans_b(20), SOFT)
    y += 44
    hrs = a["hourly"]
    if hrs:
        ch = p.bottom - y - 70
        base = y + ch
        vmax = max(150, max(h["aqi"] for h in hrs) * 1.15)
        step = p.cw / len(hrs)
        for ref in (50, 100, 150):
            ry = base - ch * ref / vmax
            p.rule(int(ry), 1, p.m, W - p.m, FAINT)
            p.text((W - p.m - 40, ry - 24), str(ref), sans(16), SOFT)
        nowh = now.hour
        for i, h in enumerate(hrs):
            x = p.m + i * step
            bh = ch * h["aqi"] / vmax
            p.d.rectangle([x + 3, base - bh, x + step - 4, base], fill=BLACK if h["hour"] == nowh else MID)
            if h["hour"] % 3 == 0:
                p.text((x, base + 10), f"{h['hour']:02d}", sans(18), SOFT)
        p.text((p.m, base + 40), "Darkest bar = the hour this paper was printed.", sans(18), SOFT)


def list_page(p, y, groups, title_font, lead, summary=True, numbered=False, balance=False):
    """Render [{"name", "items"}] groups until the page is full. Returns y."""
    n = 0
    for gi, g in enumerate(groups):
        if y + 120 > p.bottom:
            break
        # Equal share of what's left, so the last group isn't starved.
        limit = y + (p.bottom - y) / (len(groups) - gi) if balance else p.bottom
        if g.get("name"):
            p.text((p.m, y), g["name"].upper(), sans_b(22), BLACK)
            p.rule(y + 34, 1, fill=MID)
            y += 52
        for it in g["items"]:
            n += 1
            tx = p.m + (64 if numbered else 0)
            width = W - p.m - tx
            h = p.para_height(it["title"], title_font, width, lead, 3) + 8
            summ = it.get("summary") if summary else None
            if summ:
                h += p.para_height(summ, sans(23), width, 32, 2)
            meta = it.get("meta")
            if meta:
                h += 32
            if y + h > limit:
                break
            if numbered:
                p.text((p.m, y - 4), str(n), serif(44, 700), LIGHT)
            y = p.para(tx, y, it["title"], title_font, width, lead, BLACK, max_lines=3) + 6
            if summ:
                y = p.para(tx, y, summ, sans(23), width, 32, SOFT, max_lines=2)
            if meta:
                p.text((tx, y), meta, sans(20), SOFT)
                y += 32
            y += 22
        y += 14
    return y


def page_news(p, now, news):
    y = section_frame(p, now, "News", "Bengaluru, India & the World")
    groups = [{"name": g["name"], "items": [
        it | {"meta": it["date"]} for it in g["items"]]} for g in news]
    list_page(p, y, groups, serif(32, 650), 42, balance=True)


def page_hn(p, now, items):
    y = section_frame(p, now, "Technology", "Hacker News", "What developers were reading overnight.")
    groups = [{"name": "", "items": [
        {"title": it["title"], "meta": f"{it['site']}  ·  {fmt_int(it['points'])} points  ·  "
                                       f"{fmt_int(it['comments'])} comments"} for it in items]}]
    list_page(p, y, groups, serif(32, 620), 42, summary=False, numbered=True)


def page_frontend(p, now, feeds):
    y = section_frame(p, now, "Frontend", "From the Frontend",
                      "New from the blogs and newsletters of the web platform.")
    groups = [{"name": g["name"], "items": [it | {"meta": it["date"]} for it in g["items"]]} for g in feeds]
    list_page(p, y, groups, serif(30, 640), 40)


def page_github(p, now, repos):
    y = section_frame(p, now, "Open source", "Rising on GitHub",
                      "The most-starred new repositories of the past week.")
    groups = [{"name": "", "items": [
        {"title": r["name"], "summary": r["desc"],
         "meta": f"{r['lang']}  ·  {fmt_int(r['stars'])} stars"} for r in repos]}]
    list_page(p, y, groups, sans_b(30), 40, numbered=True)


def page_onthisday(p, now, events):
    y = section_frame(p, now, "History", "On This Day", now.strftime("%d %B, through the years."))
    yx = p.m
    tx = p.m + 170
    for e in events:
        h = p.para_height(e["text"], serif(30, 500), W - p.m - tx, 42, 4) + 34
        if y + h > p.bottom:
            break
        p.text((yx, y - 6), str(e["year"]), serif(48, 700), BLACK)
        y = p.para(tx, y, e["text"], serif(30, 500), W - p.m - tx, 42, INK, max_lines=4) + 34
        p.rule(y - 18, 1, tx, W - p.m, FAINT)


def page_word(p, now, wd):
    y = section_frame(p, now, "Words", "Word of the Day")
    y += 30
    f = serif(120, 700)
    while p.tw(wd["word"], f) > p.cw and f.size > 50:
        f = serif(f.size - 6, 700)
    p.text((p.m, y), wd["word"], f, BLACK)
    y += f.size + 40
    if wd.get("pos"):
        p.text((p.m, y), wd["pos"], italic(40), SOFT)
        y += 80
    p.rule(y, 2)
    y += 50
    defs = wd["definitions"]
    room = p.bottom - 80 - y
    size = 46
    while size > 30:
        lead = int(size * 1.38)
        if sum(p.para_height(dfn, serif(size), p.cw - 80, lead, 6) + size for dfn in defs) <= room:
            break
        size -= 2
    lead = int(size * 1.38)
    for i, dfn in enumerate(defs, 1):
        if y + p.para_height(dfn, serif(size), p.cw - 80, lead, 6) > p.bottom - 80:
            break
        p.text((p.m, y), f"{i}.", serif(size, 700), BLACK)
        y = p.para(p.m + 80, y, dfn, serif(size), p.cw - 80, lead, INK, max_lines=6) + size
    p.text((p.m, p.bottom - 30), "From Wiktionary's Word of the Day.", sans(20), SOFT)


def page_quote(p, now, q):
    y = section_frame(p, now, "Thought", "Quote of the Day")
    avail_top, avail_bot = y + 60, p.bottom - 160
    width = p.cw - 60
    size = 76
    while size > 34:  # largest size that fits, like a pull quote
        f = italic(size, 500)
        lead = int(size * 1.32)
        if p.para_height(q["quote"], f, width, lead) <= avail_bot - avail_top:
            break
        size -= 2
    f, lead = italic(size, 500), int(size * 1.32)
    block = p.para_height(q["quote"], f, width, lead)
    yy = avail_top + (avail_bot - avail_top - block) // 2
    p.text((p.m - 10, yy - 150), "“", serif(220, 700), LIGHT)
    yy = p.para(p.m + 30, yy, q["quote"], f, width, lead, BLACK)
    p.right(yy + 40, f"— {q['author']}", serif(40, 650), BLACK, x1=W - p.m - 30)
    p.text((p.m, p.bottom - 30), "Quote via zenquotes.io", sans(20), SOFT)


def page_comic(p, now, c):
    y = section_frame(p, now, f"Comics · xkcd #{c['num']} · {c['label']}", c["title"])
    alt_font = italic(30)
    alt_h = p.para_height(c["alt"], alt_font, p.cw, 42, 6)
    credit_y = p.bottom - 30
    img_bot = credit_y - alt_h - 70
    im = Image.open(io.BytesIO(c["image"]))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    im = im.convert("L")
    maxw, maxh = p.cw, img_bot - y
    scale = min(maxw / im.width, maxh / im.height, 2.5)
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    used = im.height + 40 + alt_h
    top = y + max(0, (credit_y - 40 - y - used) // 2)
    p.img.paste(im, ((W - im.width) // 2, top))
    ay = top + im.height + 40
    p.rule(ay - 20, 1, fill=FAINT)
    p.para(p.m, ay, c["alt"], alt_font, p.cw, 42, INK, max_lines=6)
    p.text((p.m, credit_y), "xkcd.com by Randall Munroe · CC BY-NC 2.5", sans(20), SOFT)


# ===== Assembly ===================================================================
SECTIONS = [  # (data key, contents title, renderer)
    ("weather", "Weather", page_weather),
    ("air", "Air Quality", page_air),
    ("news", "News: Bengaluru, India & World", page_news),
    ("hackernews", "Hacker News", page_hn),
    ("frontend", "From the Frontend", page_frontend),
    ("github", "Rising on GitHub", page_github),
    ("onthisday", "On This Day", page_onthisday),
    ("word", "Word of the Day", page_word),
    ("quote", "Quote of the Day", page_quote),
    ("comic", "Comics", page_comic),
]


def build(data, now):
    present = [s for s in SECTIONS if data.get(s[0])]
    total = len(present) + 1
    contents = [(title, i + 2) for i, (_, title, _) in enumerate(present)]
    pages = []
    cover = Page()
    page_cover(cover, now, data, contents)
    footer(cover, 1, total)
    pages.append(cover.img)
    for i, (key, _, fn) in enumerate(present, start=2):
        pg = Page()
        try:
            fn(pg, now, data[key])
        except Exception as exc:  # noqa: BLE001  a layout bug shouldn't sink the paper
            print(f"✗ layout {key}: {exc!r}")
            pg = Page()
            y = section_frame(pg, now, key, key.title())
            unavailable(pg, y, key.title())
        footer(pg, i, total)
        pages.append(pg.img)
    return pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--fixtures", action="store_true", help="use sample data (no network)")
    args = ap.parse_args()
    now = datetime.now(IST)

    if args.fixtures:
        from fixtures import sample_data  # noqa: PLC0415
        data = sample_data()
        status = {k: "fixture" for k in data}
    else:
        from sources import fetch_all  # noqa: PLC0415
        data, status = fetch_all(now)

    pages = build(data, now)
    out = Path(args.out)
    (out / "pages").mkdir(parents=True, exist_ok=True)
    for i, im in enumerate(pages, 1):
        im.save(out / "pages" / f"page_{i:02d}.png", optimize=True)
    pages[0].save(out / "today.png", optimize=True)
    title = f"The Mahanth Times — {now:%a %d %b %Y}"
    pages[0].save(out / "today.pdf", save_all=True, append_images=pages[1:], resolution=300.0,
                  title=title, author="The Mahanth Times")
    (out / "status.json").write_text(json.dumps({
        "printed_at": now.isoformat(timespec="seconds"), "date": now.strftime("%Y-%m-%d"),
        "title": title, "pages": len(pages), "sources": status}, indent=2))
    print(f"wrote {len(pages)} pages -> {out}/today.pdf")


if __name__ == "__main__":
    main()
