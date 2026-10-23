"""The Myles Times -- builds the full multi-page edition as a broadsheet.

    python generator/paper.py --out out              # live data
    python generator/paper.py --out out --fixtures   # sample data, no network

Outputs: out/today.pdf (all pages), out/today.png (front page), out/pages/*.png,
out/status.json (which sources worked).

Type: Chomsky (masthead, NYT-style blackletter), Old Standard (headlines),
Libre Caslon Text (body), Libre Franklin (labels). All SIL Open Font License.
"""
import argparse
import io
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from PIL import features as _pil_features

# Libre Caslon puts historical long-s ligatures (ſt, ſp) in its default "liga"
# set. Switch it off. (Without libraqm there are no ligatures to begin with.)
FEAT = ["-liga"] if _pil_features.check("raqm") else None

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"
IST = timezone(timedelta(hours=5, minutes=30))
FIRST_EDITION = datetime(2026, 10, 22, tzinfo=IST)
W, H = 1272, 1696                      # Paperwhite 12th gen framebuffer
BLACK, INK, SOFT, MID, LIGHT, FAINT, PAPER = 0, 25, 80, 120, 185, 222, 255
NAME = "The Myles Times"
SLOGAN = ("“All the Pixels", "That Fit to Print”")


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


def body(size, weight=400):          # Libre Caslon Text: body copy, figures
    return _font("LibreCaslonText.ttf", size, max(400, min(700, weight)))


def body_it(size, weight=400):
    return _font("LibreCaslonText-Italic.ttf", size, max(400, min(700, weight)))


def head(size):                      # Old Standard Bold: headlines
    return _font("OldStandard-Bold.ttf", size)


def head_it(size):                   # Old Standard Italic: decks
    return _font("OldStandard-Italic.ttf", size)


def label(size, weight=600):         # Libre Franklin: kickers, labels, folios
    return _font("LibreFranklin.ttf", size, weight)


def mast(size):                      # Chomsky: the nameplate only
    return _font("Chomsky.otf", size)


# ===== Page + layout primitives ===================================================
class Page:
    def __init__(self):
        self.img = Image.new("L", (W, H), PAPER)
        self.d = ImageDraw.Draw(self.img)
        self.m = 52
        self.cw = W - 2 * self.m
        self.bottom = H - 96
        self.links = []                  # (x0, y0, x1, y1, target page) tap targets

    def tw(self, text, font):
        return self.d.textlength(text, font=font, features=FEAT)

    def text(self, xy, text, font, fill=INK):
        self.d.text(xy, text, font=font, fill=fill, features=FEAT)

    def tracked(self, xy, text, font, spacing=2.0, fill=INK):
        """Letter-spaced caps, the way papers set kickers and folios."""
        x, y = xy
        for ch in text:
            self.d.text((x, y), ch, font=font, fill=fill)
            x += self.tw(ch, font) + spacing
        return x

    def tracked_w(self, text, font, spacing=2.0):
        return sum(self.tw(c, font) + spacing for c in text) - spacing

    def tracked_center(self, y, text, font, spacing=2.0, fill=INK, x0=None, x1=None):
        x0 = self.m if x0 is None else x0
        x1 = W - self.m if x1 is None else x1
        self.tracked((x0 + (x1 - x0 - self.tracked_w(text, font, spacing)) / 2, y), text, font, spacing, fill)

    def hline(self, y, weight=1, x0=None, x1=None, fill=BLACK):
        x0 = self.m if x0 is None else x0
        x1 = W - self.m if x1 is None else x1
        self.d.rectangle([x0, y, x1, y + weight - 1], fill=fill)

    def vline(self, x, y0, y1, weight=1, fill=BLACK):
        self.d.rectangle([x, y0, x + weight - 1, y1], fill=fill)

    def centered(self, y, text, font, fill=INK, x0=None, x1=None):
        x0 = self.m if x0 is None else x0
        x1 = W - self.m if x1 is None else x1
        self.text((x0 + (x1 - x0 - self.tw(text, font)) / 2, y), text, font, fill)

    def right(self, y, text, font, fill=INK, x1=None):
        x1 = W - self.m if x1 is None else x1
        self.text((x1 - self.tw(text, font), y), text, font, fill)

    # --- text setting -------------------------------------------------------------
    def _split_long(self, word, font, width):
        """Break a word wider than the column (repo names, URLs): after / - _ .
        first, mid-word only as a last resort. Returns the pieces."""
        if self.tw(word, font) <= width:
            return [word]
        parts = [x for x in re.findall(r"[^/\-_.]*[/\-_.]?", word) if x]
        pieces, cur = [], ""
        for part in parts:
            if self.tw(cur + part, font) <= width:
                cur += part
                continue
            if cur:
                pieces.append(cur)
            cur = ""
            for ch in part:                      # still too wide: split by characters
                if self.tw(cur + ch, font) > width and cur:
                    pieces.append(cur)
                    cur = ""
                cur += ch
        if cur:
            pieces.append(cur)
        return pieces

    def wrap(self, text, font, width, first_width=None, first_lines=0):
        """Greedy wrap; the first `first_lines` lines may be narrower (drop caps).
        Over-wide words are broken into pieces that join without a space."""
        narrow = min(width, first_width or width)
        tokens = []                              # (piece, space_before)
        for word in (text or "").split():
            for i, piece in enumerate(self._split_long(word, font, narrow)):
                tokens.append((piece, i == 0))
        lines, line = [], ""
        for piece, space in tokens:
            limit = first_width if (first_width and len(lines) < first_lines) else width
            trial = line + (" " if space and line else "") + piece
            if self.tw(trial, font) <= limit or not line:
                line = trial
            else:
                lines.append(line)
                line = piece
        if line:
            lines.append(line)
        return lines

    def _clip(self, lines, font, width, max_lines):
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            last = lines[-1]
            while last and self.tw(last + "…", font) > width:
                last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
            lines[-1] = last.rstrip(",;:") + "…"
        return lines

    def set_line(self, x, y, line, font, width, justify, fill):
        words = line.split()
        if justify and len(words) > 1:
            natural = sum(self.tw(w, font) for w in words)
            gap = (width - natural) / (len(words) - 1)
            if gap <= self.tw(" ", font) * 2.6:   # avoid ugly rivers: fall back to ragged
                cx = x
                for w in words:
                    self.text((cx, y), w, font, fill)
                    cx += self.tw(w, font) + gap
                return
        self.text((x, y), line, font, fill)

    def para(self, x, y, text, font, width, lead, fill=INK, max_lines=None, justify=False):
        lines = self._clip(self.wrap(text, font, width), font, width, max_lines)
        for i, ln in enumerate(lines):
            self.set_line(x, y, ln, font, width, justify and i < len(lines) - 1, fill)
            y += lead
        return y

    def para_h(self, text, font, width, lead, max_lines=None):
        n = len(self.wrap(text, font, width))
        return (min(n, max_lines) if max_lines else n) * lead

    def dropcap_h(self, text, font, width, lead, lines_tall=3):
        if len(text) < 60:
            return self.para_h(text, font, width, lead)
        capf = head(int(lead * lines_tall * 0.95))
        cap_w = self.tw(text[0], capf) + 10
        lines = self.wrap(text[1:].lstrip(), font, width, first_width=width - cap_w, first_lines=lines_tall)
        return max(len(lines), lines_tall) * lead

    def dropcap_para(self, x, y, text, font, width, lead, fill=INK, lines_tall=3):
        """A paragraph opening with a drop cap spanning `lines_tall` lines."""
        if len(text) < 60:
            return self.para(x, y, text, font, width, lead, fill, justify=True)
        cap, rest = text[0], text[1:].lstrip()
        capf = head(int(lead * lines_tall * 0.95))
        cap_w = self.tw(cap, capf) + 10
        self.text((x - 2, y - lead * 0.18), cap, capf, BLACK)
        lines = self.wrap(rest, font, width, first_width=width - cap_w, first_lines=lines_tall)
        for i, ln in enumerate(lines):
            lx, lw = (x + cap_w, width - cap_w) if i < lines_tall else (x, width)
            self.set_line(lx, y, ln, font, lw, i < len(lines) - 1, fill)
            y += lead
        return max(y, y + 0)


# --- column flow ---------------------------------------------------------------------
class Block:
    """Something that can be measured at a width and drawn at (x, y)."""

    def __init__(self, measure, draw):
        self.measure, self.draw = measure, draw


def _place(heights, cap, ncols, gap):
    """Greedy column placement with column height `cap`. Returns [(col, y_off)]."""
    col, y, spots = 0, 0, []
    for h in heights:
        if y > 0 and y + h > cap:
            col, y = col + 1, 0
        if col >= ncols or h > cap:
            spots.append(None)
            continue
        spots.append((col, y))
        y += h + gap
    return spots


def flow(p, blocks, x0, x1, y0, y1, ncols=2, gutter=36, rules=True, gap=18, balance=True):
    """Pour blocks into columns, newspaper style. Returns the deepest y used.

    Balanced: start from an even split (total / ncols) and grow the column height
    until everything fits, so columns end at about the same depth."""
    colw = (x1 - x0 - gutter * (ncols - 1)) / ncols
    heights = [b.measure(colw) for b in blocks]
    full = y1 - y0
    cap = full
    if balance and heights:
        cap = max(max(heights), sum(h + gap for h in heights) / ncols)
        while cap < full and None in _place(heights, cap, ncols, gap):
            cap += 8
        cap = min(cap, full)
    spots = _place(heights, cap, ncols, gap)
    col, deepest = 0, y0
    for b, h, spot in zip(blocks, heights, spots):
        if spot is None:
            continue
        col, off = spot
        b.draw(x0 + col * (colw + gutter), y0 + off, colw)
        deepest = max(deepest, y0 + off + h)
    if rules:
        for c in range(1, min(col + 1, ncols)):
            p.vline(int(x0 + c * (colw + gutter) - gutter / 2), y0, deepest, 1, MID)
    return deepest


def fit_flow(p, make_blocks, x0, x1, y0, y1, ncols=2, gutter=40, gap=26,
             scales=(1.5, 1.42, 1.35, 1.28, 1.21, 1.14, 1.08, 1.0, 0.94, 0.88)):
    """Largest type scale whose blocks fit the area in balanced columns,
    so light days get big type and busy days get denser type."""
    colw = (x1 - x0 - gutter * (ncols - 1)) / ncols
    full = y1 - y0
    for sc in scales:
        blocks = make_blocks(sc)
        heights = [b.measure(colw) for b in blocks]
        g = int(gap * sc)                     # check with the same gap we'll draw with
        if None not in _place(heights, full, ncols, g):
            return flow(p, blocks, x0, x1, y0, y1, ncols, gutter, gap=g)
    return flow(p, make_blocks(scales[-1]), x0, x1, y0, y1, ncols, gutter, gap=gap)


# ===== Shared furniture ===================================================================
def folio(p, now, n):
    """Running head on inner pages: logo, date, page number."""
    y = 30
    p.text((p.m, y - 4), NAME, mast(34), BLACK)
    p.tracked_center(y + 8, now.strftime("%A, %B %d, %Y").upper(), label(17, 500), 1.6, SOFT)
    pg = f"A{n}"
    p.right(y + 4, pg, label(24, 700), BLACK)
    p.hline(y + 48, 1)
    return y + 50


def section_head(p, now, n, kicker, title, deck=None):
    y = folio(p, now, n) + 26
    p.tracked_center(y, kicker.upper(), label(18, 650), 3, SOFT)
    y += 34
    tf = head(84)
    while p.tw(title, tf) > p.cw and tf.size > 48:
        tf = head(tf.size - 4)
    p.centered(y, title, tf, BLACK)
    y += tf.size + 22
    if deck:
        for ln in p.wrap(deck, head_it(28), p.cw - 160):
            p.centered(y, ln, head_it(28), SOFT)
            y += 36
        y += 4
    p.hline(y, 3)
    p.hline(y + 6, 1)
    return y + 30


def footer(p, n, total):
    y = H - 72
    p.hline(y, 1)
    if n == total:
        p.centered(y + 18, "— 30 —", head(26), BLACK)
        p.centered(y + 46, "That's today's paper. Tap once more to close.", body_it(19), SOFT)
    elif n == 1:
        p.tracked_center(y + 22, "TAP RIGHT FOR THE NEXT PAGE  ·  TAP LEFT TO GO BACK  ·  PRESS AND HOLD TO CLOSE",
                         label(15, 600), 1.4, SOFT)
    else:
        p.tracked_center(y + 22, f"CONTINUED  ·  A{n + 1}", label(15, 600), 1.6, SOFT)


def kicker(p, x, y, text, fill=SOFT, size=15):
    p.tracked((x, y), text.upper(), label(size, 700), 1.4, fill)
    return y + size + 10


def boxed(p, x0, y0, x1, y1, weight=1):
    p.d.rectangle([x0, y0, x1, y1], outline=BLACK, width=weight)


def temp_figure(p, x, y, value, size, fill=BLACK):
    """A big temperature, set like a newspaper: digits, then a smaller degree
    ring tucked against the last digit's ink and aligned to its top. (Old
    Standard's own degree sign carries wide side spacing that shows as a gap
    at display sizes.) Returns the x where the figure's ink ends."""
    digits = f"{value:.0f}"
    f, df = head(size), head(int(size * 0.62))
    p.text((x, y), digits, f, fill)
    bx, db = ink_bbox(digits, f), ink_bbox("°", df)
    dx = x + bx[2] + size * 0.04 - db[0]      # ring's ink starts just past the digit's ink
    dy = y + bx[1] - db[1]                     # ring's top = digits' top
    p.text((dx, dy), "°", df, fill)
    return dx + db[2]


def ink_bbox(text, font):
    """Where the ink actually lands, relative to the draw origin. (textbbox
    measures the advance box, which includes side spacing.)"""
    w = int(font.getlength(text, features=FEAT)) + font.size
    scratch = Image.new("L", (w, font.size * 2), 0)
    ImageDraw.Draw(scratch).text((font.size // 2, font.size // 2), text, font=font, fill=255, features=FEAT)
    x0, y0, x1, y1 = scratch.getbbox()
    o = font.size // 2
    return x0 - o, y0 - o, x1 - o, y1 - o


# ===== Front page =========================================================================
def page_cover(p, now, data, contents):
    from sources import WMO  # noqa: PLC0415
    w, a, q = data.get("weather"), data.get("air"), data.get("quote")
    edition = (now.date() - FIRST_EDITION.date()).days + 1

    # --- Ears + nameplate ---------------------------------------------------------
    ear_w, ear_h, top = 196, 128, 34
    lx0, rx0 = p.m, W - p.m - ear_w
    boxed(p, lx0, top, lx0 + ear_w, top + ear_h)
    sy = top + 26
    for ln in SLOGAN:
        p.centered(sy, ln, head_it(22), BLACK, lx0, lx0 + ear_w)
        sy += 30
    boxed(p, rx0, top, rx0 + ear_w, top + ear_h)
    p.tracked_center(top + 14, "WEATHER", label(14, 700), 1.6, BLACK, rx0, rx0 + ear_w)
    if w:
        ear = f"{WMO.get(w['code'], 'Mixed skies')}. High {w['max']:.0f}°, low {w['min']:.0f}°. Rain {w['rain']}%."
    else:
        ear = "Forecast unavailable this morning."
    ey = top + 38
    for ln in p.wrap(ear, body(18), ear_w - 24)[:4]:
        p.centered(ey, ln, body(18), INK, rx0, rx0 + ear_w)
        ey += 22
    room = rx0 - (lx0 + ear_w) - 40
    mf = mast(130)
    if p.tw(NAME, mf) > room:
        mf = mast(int(130 * room / p.tw(NAME, mf)))
    bbox = p.d.textbbox((0, 0), NAME, font=mf, features=FEAT)
    mh = bbox[3] - bbox[1]
    p.text(((W - (bbox[2] - bbox[0])) / 2 - bbox[0], top + (ear_h - mh) / 2 - bbox[1]), NAME, mf, BLACK)

    # --- Dateline bar between rules -------------------------------------------------------
    y = top + ear_h + 18
    p.hline(y, 1)
    f = label(17, 600)
    p.tracked((p.m, y + 12), f"VOL. I . . . No. {edition}", f, 1.4, BLACK)
    p.tracked_center(y + 12, f"BENGALURU, {now.strftime('%A, %B %d, %Y').upper()}", f, 1.4, BLACK)
    price = "FREE · ZERO SCROLLS"
    p.tracked((W - p.m - p.tracked_w(price, f, 1.4), y + 12), price, f, 1.4, BLACK)
    p.hline(y + 42, 3)
    p.hline(y + 48, 1)
    y += 70

    # --- Three columns: lead + briefing (A, B) | sidebar (C) ---------------------------------
    g = 34
    col = (p.cw - 2 * g) / 3
    ax0, ax1 = p.m, p.m + 2 * col + g
    cx0, cx1 = ax1 + g, W - p.m
    p.vline(int(ax1 + g / 2), y, p.bottom - 10, 1, MID)

    news = data.get("news") or []
    flat = [(grp["name"], it) for grp in news for it in grp["items"]]
    lead = next(((s, it) for s, it in flat if it.get("summary") and len(it["summary"]) > 60), None) \
        or (flat[0] if flat else None)
    ly = y
    if lead:
        sec, it = lead
        ly = kicker(p, ax0, ly, sec, BLACK, 16)
        ly = p.para(ax0, ly, it["title"], head(60), ax1 - ax0, 64, BLACK, max_lines=4) + 8
        ly = kicker(p, ax0, ly + 2, "By the Myles Times news desk", SOFT, 13) + 4
        if it.get("summary"):
            ly = p.dropcap_para(ax0, ly + 4, f"{sec.upper()} — {it['summary']}", body(25), ax1 - ax0, 35) + 10
        p.hline(ly + 4, 1, ax0, ax1, MID)
        ly += 24

    # The Briefing: everything else, set as two-column briefs
    p.tracked((ax0, ly), "THE BRIEFING", label(17, 800), 2, BLACK)
    p.hline(ly + 28, 2, ax0, ax1)
    ly += 44
    briefs = [(s, it) for s, it in flat if not lead or it is not lead[1]]
    for hn in (data.get("hackernews") or [])[:3]:
        briefs.append(("Technology", {"title": hn["title"], "summary": f"{hn['site']} · {hn['points']} points"}))
    blocks = [brief_block(p, s, it, title_size=28, summary_lines=3, summary_size=22) for s, it in briefs]
    flow(p, blocks, ax0, ax1, ly, p.bottom - 10, ncols=2, gutter=g)

    # --- Sidebar ----------------------------------------------------------------------------
    sy = y
    cw = cx1 - cx0
    if w:
        p.tracked((cx0, sy), "TODAY'S WEATHER", label(15, 800), 1.6, BLACK)
        p.hline(sy + 24, 2, cx0, cx1)
        sy += 36
        bx = temp_figure(p, cx0, sy - 8, w["max"], 104) + 18
        ly = p.para(bx, sy + 10, WMO.get(w["code"], "Mixed skies"), head(28), cx1 - bx, 32, BLACK, max_lines=2)
        p.text((bx, ly + 6), f"Low {w['min']:.0f}°", body(21), SOFT)      # follows the condition text
        fig_bottom = sy - 8 + ink_bbox(f"{w['max']:.0f}", head(104))[3]
        sy = max(fig_bottom, ly + 6 + 26) + 24   # table starts below whichever is taller
        for k, v in (("Rain", f"{w['rain']}%"), ("Sunrise", w["sunrise"]), ("Sunset", w["sunset"])):
            p.text((cx0, sy), k, body(21), SOFT)
            p.right(sy, v, body(21, 600), BLACK, cx1)
            sy += 30
        if a:
            p.text((cx0, sy), "Air quality", body(21), SOFT)
            p.right(sy, f"{a['aqi']:.0f} · {a['band'].split(' ')[0]}", body(21, 600), BLACK, cx1)
            sy += 30
        p.hline(sy + 8, 1, cx0, cx1, MID)
        sy += 30

    money = data.get("money")
    if money:
        usd = next((c for c in money["currencies"] if c["code"] == "USD"), money["currencies"][0])
        rupee_page = next((n for t, n in contents if t == "The Rupee"), None)
        top = sy
        sy = rupee_box(p, cx0, cx1, sy, usd, rupee_page)
        if rupee_page:
            p.links.append((cx0 - 8, top - 6, cx1 + 8, sy - 22, rupee_page))

    if q:
        p.tracked((cx0, sy), "QUOTATION OF THE DAY", label(15, 800), 1.6, BLACK)
        p.hline(sy + 24, 2, cx0, cx1)
        sy += 40
        qf, lead_q = body_it(23), 32
        lines = p._clip(p.wrap(f"“{q['quote']}”", qf, cw), qf, cw, 8)
        for i, ln in enumerate(lines):
            p.set_line(cx0, sy, ln, qf, cw, False, INK)   # ragged: narrow column
            sy += lead_q
        p.right(sy + 4, f"— {q['author']}", body(20, 600), BLACK, cx1)
        sy += 44
        p.hline(sy, 1, cx0, cx1, MID)
        sy += 22

    p.tracked((cx0, sy), "INSIDE", label(15, 800), 1.6, BLACK)
    p.hline(sy + 24, 2, cx0, cx1)
    sy += 38
    rowf = body(21)
    for title, page_no in contents:
        if sy + 30 > p.bottom - 10:
            break
        num = f"A{page_no}"
        p.text((cx0, sy), title, rowf, INK)
        nx = cx1 - p.tw(num, label(18, 700))
        dx = cx0 + p.tw(title, rowf) + 8
        while dx < nx - 10:
            p.d.rectangle([dx, sy + 18, dx + 1, sy + 19], fill=MID)
            dx += 7
        p.text((nx, sy + 2), num, label(18, 700), BLACK)
        p.links.append((cx0 - 8, sy - 3, cx1 + 8, sy + 28, page_no))
        sy += 31

    # Teasers for inner pages, while there's room
    page_of = {t: n for t, n in contents}
    teasers = []
    wd = data.get("word")
    if wd:
        teasers.append(("WORD OF THE DAY", wd["word"], (wd["definitions"] or [""])[0], page_of.get("Word of the Day")))
    otd = data.get("onthisday")
    if otd:
        e = otd[len(otd) // 2]
        teasers.append(("ON THIS DAY", str(e["year"]), e["text"], page_of.get("On This Day")))
    for kick, big, txt, pg in teasers:
        need = 36 + 44 + p.para_h(txt, body(21), cw, 29, 4) + 30
        if sy + 24 + need > p.bottom - 10:
            break
        p.hline(sy + 10, 1, cx0, cx1, MID)
        sy += 30
        if pg:
            p.links.append((cx0 - 8, sy - 6, cx1 + 8, sy + need - 20, pg))
        p.tracked((cx0, sy), kick, label(15, 800), 1.6, BLACK)
        if pg:
            p.right(sy, f"A{pg}", label(15, 800), SOFT, cx1)
        p.hline(sy + 24, 2, cx0, cx1)
        sy += 34
        p.text((cx0, sy), big, head(36), BLACK)
        sy += 46
        sy = p.para(cx0, sy, txt, body(21), cw, 29, INK, max_lines=4, justify=True)


def brief_block(p, section, it, title_size=30, summary_lines=3, numbered=None, summary_size=24):
    tf, sf = head(title_size), body(summary_size)
    lead_t, lead_s = int(title_size * 1.17), int(summary_size * 1.38)
    nw = 60 if numbered else 0      # room for "12"

    def measure(width):
        h = 24 + p.para_h(it["title"], tf, width - nw, lead_t, 4) + 4
        if it.get("summary"):
            h += p.para_h(it["summary"], sf, width - nw, lead_s, summary_lines)
        return h

    def draw(x, y, width):
        tx, tw_ = x + nw, width - nw
        if numbered:
            p.text((x, y + 16), str(numbered), head(38), LIGHT)
        kicker(p, tx, y, section, SOFT, 13)
        yy = p.para(tx, y + 24, it["title"], tf, tw_, lead_t, BLACK, max_lines=4) + 4
        if it.get("summary"):
            p.para(tx, yy, it["summary"], sf, tw_, lead_s, INK, max_lines=summary_lines, justify=True)

    return Block(measure, draw)


# ===== Inner pages ==============================================================================
def list_page(p, y, items, ncols=2, title_size=32, summary_lines=4, numbered=False, summary_size=25):
    def make(sc):
        return [brief_block(p, sec, it, int(title_size * sc), summary_lines + (2 if sc > 1.2 else 0),
                            numbered=(i + 1) if numbered else None, summary_size=int(summary_size * sc))
                for i, (sec, it) in enumerate(items)]
    fit_flow(p, make, p.m, W - p.m, y, p.bottom - 6, ncols=ncols)


def page_news(p, now, n, news):
    y = section_head(p, now, n, "News", "Bengaluru, India & the World",
                     "The morning's headlines from home and abroad.")
    items = []
    for g in news:  # interleave a little so every section reaches the page
        for it in g["items"]:
            items.append((g["name"], it | {"summary": " · ".join(x for x in (it.get("date"), it.get("summary")) if x)}))
    list_page(p, y, items, title_size=33, summary_lines=4)


def page_hn(p, now, n, items):
    y = section_head(p, now, n, "Technology", "Hacker News", "What developers were reading overnight.")
    rows = [(it["site"], {"title": it["title"],
                          "summary": f"{it['points']:,} points · {it['comments']:,} comments"})
            for it in items]
    list_page(p, y, rows, title_size=31, summary_lines=1, numbered=True)


def page_frontend(p, now, n, feeds):
    y = section_head(p, now, n, "The Web Platform", "From the Frontend",
                     "New from the blogs and newsletters of the frontend world.")
    rows = [(g["name"], it | {"summary": " · ".join(x for x in (it.get("date"), it.get("summary")) if x)})
            for g in feeds for it in g["items"]]
    list_page(p, y, rows, title_size=31, summary_lines=4)


def page_github(p, now, n, repos):
    y = section_head(p, now, n, "Open Source", "Rising on GitHub", "The most-starred new repositories of the past week.")
    rows = [(f"{r['lang']} · {r['stars']:,} stars", {"title": r["name"], "summary": r["desc"]}) for r in repos]
    list_page(p, y, rows, title_size=30, summary_lines=3, numbered=True)


def page_weather(p, now, n, w):
    from sources import WMO  # noqa: PLC0415
    y = section_head(p, now, n, "Weather · Thanisandra, Bengaluru", "The Weather Report",
                     f"{WMO.get(w['code'], 'Mixed skies')}, with a high of {w['max']:.0f}° "
                     f"and a {w['rain']}% chance of rain.")
    # Big figure + stat table, side by side, boxed
    boxed(p, p.m, y, W - p.m, y + 250)
    hx = temp_figure(p, p.m + 28, y + 18, w["max"], 210) + 30      # clear of the box's top edge
    p.text((hx, y + 52), "HIGH", label(16, 700), SOFT)
    p.text((hx, y + 74), f"{w['max']:.1f}°C", body(30, 600), BLACK)
    p.text((hx, y + 128), "LOW", label(16, 700), SOFT)
    p.text((hx, y + 150), f"{w['min']:.1f}°C", body(30, 600), BLACK)
    tx = W // 2 + 30
    p.vline(tx - 30, y + 20, y + 230, 1, MID)
    stats = [("Rain", f"{w['rain']}% · {w['rain_mm']:.1f} mm"), ("Humidity", f"{w['humidity']}%"),
             ("Wind", f"up to {w['wind_max']:.0f} km/h"), ("UV index", f"{w['uv']:.0f}"),
             ("Sunrise", w["sunrise"]), ("Sunset", w["sunset"])]
    ty = y + 26
    for k, v in stats:
        p.text((tx, ty), k, body(23), SOFT)
        p.right(ty, v, body(23, 600), BLACK, W - p.m - 24)
        ty += 34
    y += 270

    tips = []
    if w["rain"] >= 40:
        tips.append("carry an umbrella")
    if w["uv"] >= 7 and w["rain"] < 60:
        tips.append("sunscreen if you're out midday")
    if w["max"] >= 32:
        tips.append("stay hydrated")
    if not tips:
        tips.append("a good day to be outside")
    p.centered(y, "Advice: " + ", ".join(tips) + ".", head_it(30), BLACK)
    y += 52
    p.hline(y, 1, fill=MID)
    y += 22

    # Hourly: temperature line, rain strip below
    p.tracked((p.m, y), "HOUR BY HOUR", label(16, 800), 1.6, BLACK)
    y += 34
    hrs = w["hourly"]
    if hrs:
        cx0, cx1 = p.m + 64, W - p.m - 28   # room for the last rain bar
        ch = 220
        base = y + 30 + ch
        temps = [h["temp"] for h in hrs]
        lo, hi = min(temps) - 1, max(temps) + 1
        step = (cx1 - cx0) / max(1, len(hrs) - 1)
        for gi in range(3):
            gyy = base - gi * ch / 2
            p.hline(int(gyy), 1, cx0, cx1, FAINT)
            p.text((p.m, gyy - 12), f"{lo + gi * (hi - lo) / 2:.0f}°", body(18), SOFT)
        pts = [(cx0 + i * step, base - (h["temp"] - lo) / (hi - lo) * ch) for i, h in enumerate(hrs)]
        p.d.line(pts, fill=BLACK, width=4, joint="curve")
        for i, (x, yy) in enumerate(pts):
            if hrs[i]["hour"] % 3 == 0:
                p.d.ellipse([x - 6, yy - 6, x + 6, yy + 6], fill=BLACK)
                lbl = f"{hrs[i]['temp']:.0f}°"
                p.text((x - p.tw(lbl, body(20, 700)) / 2, yy - 36), lbl, body(20, 700), BLACK)
        ry0, rh = base + 26, 80
        p.text((p.m, ry0 + rh / 2 - 12), "Rain", label(16, 600), SOFT)
        bw = step * 0.6
        for i, h in enumerate(hrs):
            x = cx0 + i * step
            r = h["rain"] or 0
            p.d.rectangle([x - bw / 2, ry0, x + bw / 2, ry0 + rh], outline=FAINT)
            if r:
                p.d.rectangle([x - bw / 2, ry0 + rh * (1 - r / 100), x + bw / 2, ry0 + rh], fill=MID)
            if h["hour"] % 3 == 0:
                rl = f"{r}%"
                p.text((x - p.tw(rl, label(16, 500)) / 2, ry0 + rh + 8), rl, label(16, 500), INK)
                hl = f"{h['hour']:02d}:00"
                p.text((x - p.tw(hl, label(16, 500)) / 2, ry0 + rh + 32), hl, label(16, 500), SOFT)
        y = ry0 + rh + 70
    p.hline(y, 1, fill=MID)
    y += 22

    # Outlook: boxed days
    p.tracked((p.m, y), "THE OUTLOOK", label(16, 800), 1.6, BLACK)
    y += 36
    days = w["days"][1:4]
    colw = (p.cw - 2 * 20) / 3
    for i, dday in enumerate(days):
        x = p.m + i * (colw + 20)
        boxed(p, x, y, x + colw, y + 190)
        dt = datetime.strptime(dday["date"], "%Y-%m-%d")
        p.centered(y + 12, dt.strftime("%A"), head(32), BLACK, x, x + colw)
        p.centered(y + 56, f"{dday['max']:.0f}° / {dday['min']:.0f}°", body(32, 600), BLACK, x, x + colw)
        p.centered(y + 104, WMO.get(dday["code"], "—"), body_it(24), INK, x, x + colw)
        p.centered(y + 146, f"Rain {dday['rain']}%", label(19, 600), SOFT, x, x + colw)
    y += 190 + 26
    almanac(p, now, w, y)


def page_air(p, now, n, a):
    from sources import AQI_BANDS  # noqa: PLC0415
    y = section_head(p, now, n, "Air Quality · Thanisandra", "The Air We Breathe", a["advice"])
    big = f"{a['aqi']:.0f}"
    p.text((p.m, y - 14), big, head(230), BLACK)
    bx = p.m + p.tw(big, head(230)) + 30
    p.text((bx, y + 46), "US AIR QUALITY INDEX", label(17, 700), SOFT)
    p.para(bx, y + 76, a["band"], head(54), W - p.m - bx, 60, BLACK, max_lines=2)
    y += 290

    p.tracked((p.m, y), "WHERE TODAY SITS", label(16, 800), 1.6, BLACK)
    y += 36
    edges = [0, 50, 100, 150, 200, 300, 400]
    shades = [235, 205, 170, 130, 90, 50]
    gx0, gx1, gh = p.m, W - p.m, 50
    span = gx1 - gx0
    pos = lambda v: gx0 + span * min(v, 400) / 400  # noqa: E731
    for i in range(6):
        p.d.rectangle([pos(edges[i]), y, pos(edges[i + 1]) - 3, y + gh], fill=shades[i])
        p.text((pos(edges[i]) + 4, y + gh + 8), str(edges[i]), label(16, 500), SOFT)
    mx = pos(a["aqi"])
    p.d.polygon([(mx - 15, y - 18), (mx + 15, y - 18), (mx, y + 2)], fill=BLACK)
    p.d.rectangle([mx - 2, y, mx + 2, y + gh], fill=BLACK)
    y += gh + 40
    names = [b[1] for b in AQI_BANDS]
    p.para(p.m, y, "  ·  ".join(f"{e}–{edges[i + 1]} {names[i]}" for i, e in enumerate(edges[:-2])),
           body_it(19), p.cw, 26, SOFT)
    y += 64
    p.hline(y, 1, fill=MID)
    y += 22

    p.tracked((p.m, y), "WHAT'S IN THE AIR · µg/m³", label(16, 800), 1.6, BLACK)
    y += 40
    pol = [("PM2.5", a["pm2_5"], "fine particles"), ("PM10", a["pm10"], "dust, pollen"),
           ("O₃", a["o3"], "ozone"), ("NO₂", a["no2"], "traffic exhaust"), ("CO", a["co"], "carbon monoxide")]
    colw = p.cw / 5
    for i, (name, val, what) in enumerate(pol):
        x = p.m + i * colw
        if i:
            p.vline(int(x - 10), y, y + 140, 1, FAINT)
        p.text((x, y), name, body(24, 700), BLACK)           # Caslon has ₂ ₃
        p.text((x, y + 34), "—" if val is None else f"{val:.0f}", head(60), BLACK)
        p.text((x, y + 108), what, body_it(19), SOFT)
    y += 160
    p.hline(y, 1, fill=MID)
    y += 22

    p.tracked((p.m, y), "AQI THROUGH THE DAY", label(16, 800), 1.6, BLACK)
    y += 40
    hrs = a["hourly"]
    if hrs:
        ch = p.bottom - y - 70
        base = y + ch
        vmax = max(150, max(h["aqi"] for h in hrs) * 1.15)
        step = p.cw / len(hrs)
        for ref in (50, 100, 150):
            ry = base - ch * ref / vmax
            p.hline(int(ry), 1, p.m, W - p.m, FAINT)
            p.text((W - p.m - 40, ry - 24), str(ref), label(15, 500), SOFT)
        for i, h in enumerate(hrs):
            x = p.m + i * step
            bh = ch * h["aqi"] / vmax
            p.d.rectangle([x + 3, base - bh, x + step - 4, base], fill=BLACK if h["hour"] == now.hour else MID)
            if h["hour"] % 3 == 0:
                p.text((x, base + 10), f"{h['hour']:02d}", label(16, 500), SOFT)
        p.text((p.m, base + 38), "The black bar marks the hour this paper went to press.", body_it(18), SOFT)


def page_onthisday(p, now, n, events):
    y = section_head(p, now, n, "History", "On This Day", now.strftime("%B %d, through the years."))
    def make(sc):
        yf, bf, lead = head(int(40 * sc)), body(int(27 * sc)), int(38 * sc)
        blocks = []
        for e in events:
            def measure(width, e=e):
                return yf.size + 10 + p.para_h(e["text"], bf, width, lead, 8)

            def draw(x, yy, width, e=e):
                p.text((x, yy - 4), str(e["year"]), yf, BLACK)
                p.hline(int(yy + yf.size), 1, x + p.tw(str(e["year"]), yf) + 12, x + width, FAINT)
                p.para(x, yy + yf.size + 10, e["text"], bf, width, lead, INK, max_lines=8, justify=True)
            blocks.append(Block(measure, draw))
        return blocks
    fit_flow(p, make, p.m, W - p.m, y, p.bottom - 6, ncols=2, gap=32)


def page_word(p, now, n, wd):
    y = section_head(p, now, n, "Words", "Word of the Day")
    y += 30
    f = head(124)
    while p.tw(wd["word"], f) > p.cw and f.size > 50:
        f = head(f.size - 6)
    p.centered(y, wd["word"], f, BLACK)
    y += f.size + 30
    if wd.get("pos"):
        p.centered(y, wd["pos"], body_it(38), SOFT)
        y += 70
    p.hline(y, 1, p.m + 300, W - p.m - 300)
    y += 50
    defs = wd["definitions"]
    room = p.bottom - 80 - y
    size = 44
    while size > 28:
        lead = int(size * 1.4)
        if sum(p.para_h(d, body(size), p.cw - 90, lead, 6) + size for d in defs) <= room:
            break
        size -= 2
    lead = int(size * 1.4)
    for i, dfn in enumerate(defs, 1):
        if y + p.para_h(dfn, body(size), p.cw - 90, lead, 6) > p.bottom - 80:
            break
        p.text((p.m + 10, y - 2), f"{i}.", head(size), BLACK)
        y = p.para(p.m + 90, y, dfn, body(size), p.cw - 90, lead, INK, max_lines=6, justify=True) + size
    p.centered(p.bottom - 34, "From Wiktionary's Word of the Day", body_it(19), SOFT)


def page_quote(p, now, n, q):
    y = section_head(p, now, n, "Thought", "Quotation of the Day")
    top, bot = y + 60, p.bottom - 170
    width = p.cw - 120
    size = 72
    while size > 34:
        if p.para_h(q["quote"], body_it(size), width, int(size * 1.35)) <= bot - top:
            break
        size -= 2
    qf, lead = body_it(size), int(size * 1.35)
    block = p.para_h(q["quote"], qf, width, lead)
    yy = top + (bot - top - block) // 2
    p.text((p.m + 4, yy - 120), "“", head(200), LIGHT)
    yy = p.para(p.m + 60, yy, q["quote"], qf, width, lead, BLACK)
    p.hline(yy + 26, 1, W - p.m - 360, W - p.m - 60)
    p.right(yy + 44, f"— {q['author']}", head(40), BLACK, x1=W - p.m - 60)
    p.centered(p.bottom - 34, "Quote via zenquotes.io", body_it(19), SOFT)


def page_comic(p, now, n, c):
    y = section_head(p, now, n, f"The Funny Pages · xkcd #{c['num']} · {c['label']}", c["title"])
    alt_font = body_it(27)
    alt_h = p.para_h(c["alt"], alt_font, p.cw - 80, 38, 6)
    credit_y = p.bottom - 34
    img_bot = credit_y - alt_h - 90
    im = Image.open(io.BytesIO(c["image"]))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    im = im.convert("L")
    maxw, maxh = p.cw - 40, img_bot - y - 20
    scale = min(maxw / im.width, maxh / im.height, 2.5)
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    used = im.height + 50 + alt_h
    top = y + max(0, (credit_y - 50 - y - used) // 2)
    x = (W - im.width) // 2
    p.img.paste(im, (x, top))
    boxed(p, x - 14, top - 14, x + im.width + 14, top + im.height + 14)
    ay = top + im.height + 44
    lines = p._clip(p.wrap(c["alt"], alt_font, p.cw - 80), alt_font, p.cw - 80, 6)
    for ln in lines:
        p.centered(ay, ln, alt_font, INK)
        ay += 38
    p.centered(credit_y, "xkcd.com by Randall Munroe · CC BY-NC 2.5", body_it(19), SOFT)


# ===== Money: sidebar box + The Rupee page ==========================================================
def change_marker(p, x, y, up, size=14):
    """A small up/down triangle (no font has a reliable arrow glyph)."""
    if up:
        p.d.polygon([(x, y + size + 2), (x + size, y + size + 2), (x + size / 2, y + 4)], fill=BLACK)
    else:
        p.d.polygon([(x, y + 5), (x + size, y + 5), (x + size / 2, y + size + 3)], fill=BLACK)


def sparkline(p, x0, y0, x1, h, vals, width=3):
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    pts = [(x0 + i * (x1 - x0) / max(1, len(vals) - 1), y0 + h - (v - lo) / span * h) for i, v in enumerate(vals)]
    p.hline(int(y0 + h), 1, x0, x1, FAINT)
    p.d.line(pts, fill=BLACK, width=width, joint="curve")
    for x, y in (pts[0], pts[-1]):
        p.d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=BLACK)


def rupee_box(p, cx0, cx1, sy, usd, page_no=None):
    p.tracked((cx0, sy), "RUPEE WATCH", label(15, 800), 1.6, BLACK)
    if page_no:
        p.right(sy, f"A{page_no}", label(15, 800), SOFT, cx1)
    p.hline(sy + 24, 2, cx0, cx1)
    sy += 38
    p.text((cx0, sy + 8), "US$1 =", body(22), SOFT)
    p.right(sy - 4, f"Rs {usd['rate']:.2f}", head(38), BLACK, cx1)
    sy += 48
    diff = usd["rate"] - usd["prev"]
    change_marker(p, cx0, sy, diff >= 0)
    prev_day = datetime.strptime(usd["series"][-2][0], "%Y-%m-%d").strftime("%a")
    p.text((cx0 + 22, sy), f"{abs(diff):.2f} since {prev_day}", body(20), INK)
    sy += 34
    sparkline(p, cx0, sy, cx1, 46, [v for _, v in usd["series"]])
    sy += 46 + 12
    p.text((cx0, sy), "Euro, pound, yen and more inside", body_it(18), SOFT)
    sy += 34
    p.hline(sy, 1, cx0, cx1, MID)
    return sy + 22


def page_money(p, now, n, money):
    when = datetime.strptime(money["date"], "%Y-%m-%d").strftime("%A, %d %B")
    y = section_head(p, now, n, "Markets · Indian Rupee", "The Rupee",
                     f"What each currency cost in rupees at the last fixing, {when}.")
    rows = money["currencies"]
    cols = [p.m, p.m + 380, p.m + 600, p.m + 830]          # currency | rupees | change | trend
    for x, t in zip(cols, ("CURRENCY", "RUPEES", "CHANGE", "LAST 8 TRADING DAYS")):
        p.text((x, y), t, label(15, 700), SOFT)
    y += 30
    p.hline(y, 2)
    room = p.bottom - 90 - y
    rh = max(96, min(124, room // max(1, len(rows))))
    for i, c in enumerate(rows):
        ry = y + i * rh
        if ry + rh > p.bottom - 80:
            break
        mid = ry + rh // 2
        unit = f"{c['units']} " if c["units"] != 1 else "1 "
        p.text((cols[0], mid - 30), c["name"], head(32), BLACK)
        p.text((cols[0], mid + 10), f"{unit}{c['code']}", label(17, 700), SOFT)
        p.text((cols[1], mid - 24), f"Rs {c['rate']:.2f}", body(34, 700), BLACK)
        diff = c["rate"] - c["prev"]
        pct = diff / c["prev"] * 100 if c["prev"] else 0
        change_marker(p, cols[2], mid - 18, diff >= 0, 16)
        p.text((cols[2] + 26, mid - 22), f"{abs(diff):.2f}", body(27, 600), BLACK)
        p.text((cols[2] + 26, mid + 12), f"{abs(pct):.2f}%", body(20), SOFT)
        sparkline(p, cols[3], mid - 30, W - p.m, 56, [v for _, v in c["series"]], width=3)
        p.hline(ry + rh, 1, fill=FAINT)
    p.para(p.m, p.bottom - 66, "European Central Bank reference rates, fixed around 16:00 CET on working days. "
           "Change is since the previous fixing; a down arrow means the rupee gained against that currency.",
           body_it(19), p.cw, 26, SOFT, max_lines=2)


# ===== Almanac: day length + moon ==================================================================
SYNODIC = 29.530588853
PHASES = [(1.85, "New moon"), (5.54, "Waxing crescent"), (9.23, "First quarter"), (12.92, "Waxing gibbous"),
          (16.61, "Full moon"), (20.30, "Waning gibbous"), (23.99, "Last quarter"), (27.68, "Waning crescent"),
          (99, "New moon")]


def moon_info(now):
    """Moon age in days since the last new moon (reference new moon: 6 Jan 2000, 18:14 UTC)."""
    ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    age = ((now - ref).total_seconds() / 86400) % SYNODIC
    illum = (1 - math.cos(2 * math.pi * age / SYNODIC)) / 2
    name = next(nm for limit, nm in PHASES if age < limit)
    full = now + timedelta(days=(SYNODIC / 2 - age) % SYNODIC)
    return age, illum, name, full


def draw_moon(p, cx, cy, r, age):
    """Lit part right while waxing, left while waning; terminator at w*cos(phase angle)."""
    theta = 2 * math.pi * age / SYNODIC
    for dy in range(-r, r + 1):
        w = math.sqrt(max(0, r * r - dy * dy))
        xt = w * math.cos(theta)
        p.d.line([(cx - w, cy + dy), (cx + w, cy + dy)], fill=70)            # dark side
        lit = (xt, w) if age < SYNODIC / 2 else (-w, -xt)
        if lit[1] > lit[0]:
            p.d.line([(cx + lit[0], cy + dy), (cx + lit[1], cy + dy)], fill=PAPER)
    p.d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=BLACK, width=2)


def almanac(p, now, w, y):
    if y + 170 > p.bottom - 6:
        return
    p.hline(y - 12, 1, fill=MID)
    p.tracked((p.m, y), "THE ALMANAC", label(16, 800), 1.6, BLACK)
    y += 38
    colw = p.cw / 3
    sr, ss = (datetime.strptime(t, "%H:%M") for t in (w["sunrise"], w["sunset"]))
    mins = int((ss - sr).total_seconds() // 60)
    p.text((p.m, y), "DAY LENGTH", label(15, 700), SOFT)
    p.text((p.m, y + 24), f"{mins // 60} h {mins % 60:02d} m", head(46), BLACK)
    p.text((p.m, y + 84), f"Sunrise {w['sunrise']} · Sunset {w['sunset']}", body(20), INK)
    age, illum, name, full = moon_info(now)
    mx = p.m + colw + 20
    draw_moon(p, int(mx + 48), int(y + 56), 48, age)
    p.text((mx + 116, y), "MOON", label(15, 700), SOFT)
    p.para(mx + 116, y + 24, name, head(30), colw - 136, 34, BLACK, max_lines=2)
    p.text((mx + 116, y + 96), f"{illum * 100:.0f}% illuminated", body(20), INK)
    fx = p.m + 2 * colw + 20
    p.text((fx, y), "NEXT FULL MOON", label(15, 700), SOFT)
    days = (full.date() - now.date()).days
    p.text((fx, y + 24), full.strftime("%a %d %b"), head(40), BLACK)
    p.text((fx, y + 84), "tonight" if days <= 0 else f"in {days} day{'s' if days != 1 else ''}", body(20), INK)
    for x in (p.m + colw, p.m + 2 * colw):
        p.vline(int(x), y - 4, y + 118, 1, FAINT)


# ===== Featured article + picture of the day =======================================================
def page_article(p, now, n, art):
    y = section_head(p, now, n, "Featured Article · From Wikipedia", art["title"], art.get("description") or None)
    paras = [t for t in art["paragraphs"] if t]

    def make(sc):
        f, lead, indent = body(int(26 * sc)), int(37 * sc), int(34 * sc)
        blocks = []
        for i, txt in enumerate(paras):
            if i == 0:   # opens with a drop cap
                blocks.append(Block(lambda wd, t=txt: p.dropcap_h(t, f, wd, lead),
                                    lambda x, yy, wd, t=txt: p.dropcap_para(x, yy, t, f, wd, lead)))
                continue

            def measure(wd, t=txt):
                return len(p.wrap(t, f, wd, first_width=wd - indent, first_lines=1)) * lead

            def draw(x, yy, wd, t=txt):   # first-line indent, justified: newspaper paragraphs
                lines = p.wrap(t, f, wd, first_width=wd - indent, first_lines=1)
                for k, ln in enumerate(lines):
                    lx, lw = (x + indent, wd - indent) if k == 0 else (x, wd)
                    p.set_line(lx, yy, ln, f, lw, k < len(lines) - 1, INK)
                    yy += lead
            blocks.append(Block(measure, draw))
        return blocks
    fit_flow(p, make, p.m, W - p.m, y, p.bottom - 56, ncols=2, gap=10,
             scales=(1.3, 1.24, 1.18, 1.12, 1.06, 1.0, 0.95, 0.9, 0.85, 0.8))
    p.centered(p.bottom - 34, "From Wikipedia, the free encyclopedia · CC BY-SA 4.0", body_it(19), SOFT)


def halftone(im, cell=7, angle=45):
    """Newspaper halftone: one dot per cell, dot AREA proportional to darkness, on a grid
    tilted 45 degrees (the eye notices diagonal patterns least). Drawn 4x oversized, then
    shrunk, so the dots come out round and smooth."""
    S = 4
    im = ImageOps.autocontrast(im.convert("L"), cutoff=1)
    w0, h0 = im.size
    big = im.rotate(angle, expand=True, fillcolor=255)
    grid = big.resize((max(1, big.width // cell), max(1, big.height // cell)), Image.BOX)  # mean per cell
    dots = Image.new("L", (grid.width * cell * S, grid.height * cell * S), 255)
    d = ImageDraw.Draw(dots)
    g = grid.load()
    half = cell * S / 2
    for gy in range(grid.height):
        for gx in range(grid.width):
            dark = 1 - g[gx, gy] / 255
            if dark < 0.04:
                continue
            r = half * math.sqrt(dark) * 1.2      # area ~ darkness; full black just overlaps
            cx, cy = (gx + 0.5) * cell * S, (gy + 0.5) * cell * S
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=0)
    back = dots.rotate(-angle, expand=True, fillcolor=255)
    bw, bh = back.size
    left, top = (bw - w0 * S) // 2, (bh - h0 * S) // 2
    return back.crop((left, top, left + w0 * S, top + h0 * S)).resize((w0, h0), Image.LANCZOS)


def page_picture(p, now, n, pic):
    y = section_head(p, now, n, "Picture of the Day · Wikimedia Commons", pic["title"] or "Picture of the Day")
    cap_f, cap_lead = body_it(25), 35
    cap_h = p.para_h(pic.get("caption") or "", cap_f, p.cw, cap_lead, 5)
    credit_y = p.bottom - 34
    img_bot = credit_y - cap_h - 70
    im = Image.open(io.BytesIO(pic["image"]))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    im = im.convert("L")
    maxw, maxh = p.cw, img_bot - y - 10
    scale = min(maxw / im.width, maxh / im.height)
    im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
    ht = halftone(im)
    x = (W - ht.width) // 2
    top = y + max(0, (img_bot - y - ht.height) // 2)
    p.img.paste(ht, (x, top))
    boxed(p, x - 1, top - 1, x + ht.width, top + ht.height)
    cy = top + ht.height + 26
    if pic.get("caption"):
        p.para(p.m, cy, pic["caption"], cap_f, p.cw, cap_lead, INK, max_lines=5, justify=True)
    credit = " · ".join(t for t in (f"Photo: {pic['artist']}" if pic.get("artist") else "",
                                     pic.get("license") or "", "via Wikimedia Commons") if t)
    p.centered(credit_y, credit, body_it(19), SOFT)



# ===== Assembly ===================================================================================
SECTIONS = [  # (data key, index title, renderer)
    ("weather", "Weather", page_weather),
    ("air", "Air Quality", page_air),
    ("news", "News", page_news),
    ("money", "The Rupee", page_money),
    ("hackernews", "Hacker News", page_hn),
    ("frontend", "Frontend", page_frontend),
    ("github", "Rising on GitHub", page_github),
    ("article", "Featured Article", page_article),
    ("picture", "Picture of the Day", page_picture),
    ("onthisday", "On This Day", page_onthisday),
    ("word", "Word of the Day", page_word),
    ("quote", "Quotation", page_quote),
    ("comic", "The Funny Pages", page_comic),
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
    links = [(1,) + link for link in cover.links]
    for i, (key, title, fn) in enumerate(present, start=2):
        pg = Page()
        try:
            fn(pg, now, i, data[key])
        except Exception as exc:  # noqa: BLE001  a layout bug shouldn't sink the paper
            print(f"✗ layout {key}: {exc!r}")
            pg = Page()
            y = section_head(pg, now, i, key, title)
            pg.para(pg.m, y + 40, f"{title} could not be set this morning. It will be back tomorrow.",
                    body_it(34), pg.cw, 48, SOFT)
        footer(pg, i, total)
        pages.append(pg.img)
    return pages, links


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

    pages, links = build(data, now)
    out = Path(args.out)
    (out / "pages").mkdir(parents=True, exist_ok=True)
    for old in (out / "pages").glob("page_*.png"):
        old.unlink()
    for i, im in enumerate(pages, 1):
        im.save(out / "pages" / f"page_{i:02d}.png", optimize=True)
    pages[0].save(out / "today.png", optimize=True)
    title = f"{NAME} — {now:%a %d %b %Y}"
    pages[0].save(out / "today.pdf", save_all=True, append_images=pages[1:], resolution=300.0,
                  title=title, author=NAME)
    # Tap targets for the Kindle viewer: "page x0 y0 x1 y1 target", in permille of the screen
    (out / "links.txt").write_text("".join(
        f"{pg} {round(x0 * 1000 / W)} {round(y0 * 1000 / H)} {round(x1 * 1000 / W)} {round(y1 * 1000 / H)} {t}\n"
        for pg, x0, y0, x1, y1, t in links))
    (out / "status.json").write_text(json.dumps({
        "printed_at": now.isoformat(timespec="seconds"), "date": now.strftime("%Y-%m-%d"),
        "title": title, "pages": len(pages), "sources": status}, indent=2))
    print(f"wrote {len(pages)} pages -> {out}/today.pdf")


if __name__ == "__main__":
    main()
