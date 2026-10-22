"""The Mahanth Times -- front page renderer.

Renders an 8-bit grayscale PNG (no alpha) at the Kindle's native resolution,
which is the format eips/FBInk draw fastest and cleanest.

    python generator/render.py --out out             # today's paper
    python generator/render.py --out out --test      # the static test page

Right now the paper carries placeholder stories; step 2 wires in real data.
"""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"
IST = timezone(timedelta(hours=5, minutes=30))
FIRST_EDITION = datetime(2026, 10, 22, tzinfo=IST)  # No. 001

BLACK, INK, MID, PAPER = 0, 34, 119, 255


# --- Type helpers -------------------------------------------------------------
def lora(size, weight=500, italic=False):
    f = ImageFont.truetype(str(FONTS / ("Lora-Italic-Variable.ttf" if italic else "Lora-Variable.ttf")), size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:  # older FreeType without variable-font support
        pass
    return f


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def wrap(draw, text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def para(draw, xy, text, fnt, width, leading, fill=INK):
    x, y = xy
    for ln in wrap(draw, text, fnt, width):
        draw.text((x, y), ln, font=fnt, fill=fill)
        y += leading
    return y


def centered(draw, y, text, fnt, w, fill=INK):
    draw.text(((w - draw.textlength(text, font=fnt)) / 2, y), text, font=fnt, fill=fill)


# --- Content ------------------------------------------------------------------
def placeholder_content(now):
    return {
        "headline": "Paper Arrives From GitHub; Phone Remains Face-Down",
        "deck": "A robot newsroom in the cloud set this page at dawn, and a jailbroken "
                "Paperwhite fetched it before anyone reached for a phone.",
        "story": [
            "BENGALURU — The Mahanth Times went to press this morning without a "
            "single human awake. A GitHub Actions job rendered this page, published it, "
            "and went back to sleep.",
            "If the time in the footer is from this morning, the whole chain works: "
            "cloud renderer, GitHub hosting, Kindle download, e-ink draw.",
            "Coming soon to these columns: your calendar, your inbox highlights, the "
            "weather, and whatever else earns a place on the front page.",
        ],
    }


# --- Page ---------------------------------------------------------------------
def render(w, h, now, test=False):
    s = w / 1072
    S = lambda v: max(1, round(v * s))  # noqa: E731  scale from the 1072px design
    img = Image.new("L", (w, h), PAPER)
    d = ImageDraw.Draw(img)
    sans = font("Inter-Regular.otf", S(22))
    sans_b = font("Inter-SemiBold.otf", S(22))
    small = font("Inter-Regular.otf", S(18))
    m = S(56)
    col_w = w - 2 * m
    edition = (now.date() - FIRST_EDITION.date()).days + 1
    c = placeholder_content(now)
    if test:
        c["headline"] = "Kindle Receives First Edition; Phone Remains Face-Down"

    # Masthead
    y = S(48)
    d.text((m, y), f"{'TEST EDITION' if test else 'MORNING EDITION'}  ·  NO. {edition:03d}", font=sans_b, fill=INK)
    right = "PRICE: ZERO SCROLLS"
    d.text((w - m - d.textlength(right, font=sans_b), y), right, font=sans_b, fill=INK)
    y += S(42)
    mast = lora(S(112), weight=700)
    title = "The Mahanth Times"
    tw = d.textlength(title, font=mast)
    if tw > col_w:
        mast = lora(int(S(112) * col_w / tw), weight=700)
    centered(d, y, title, mast, w, fill=BLACK)
    y += mast.size + S(26)
    d.rectangle([m, y, w - m, y + S(5)], fill=BLACK)
    y += S(14)
    centered(d, y, now.strftime("%A, %d %B %Y").upper() + "  ·  BENGALURU  ·  PRINTED ON E-INK", sans, w)
    y += S(38)
    d.rectangle([m, y, w - m, y + S(2)], fill=BLACK)
    y += S(40)

    # Lead story
    y = para(d, (m, y), c["headline"], font("DejaVuSerif-Bold.ttf", S(58)), col_w, S(70), fill=BLACK)
    y += S(14)
    y = para(d, (m, y), c["deck"], lora(S(30), 500, italic=True), col_w, S(42))
    y += S(28)

    gap = S(40)
    left_w = int(col_w * 0.56)
    rx = m + left_w + gap
    right_w = w - m - rx
    top = y
    body = lora(S(27), weight=520)
    for p in c["story"]:
        y = para(d, (m, y), p, body, left_w, S(40)) + S(16)
    d.rectangle([m + left_w + gap // 2 - S(1), top, m + left_w + gap // 2, max(y, top + S(560))], fill=MID)

    # Right column: e-ink calibration (kept until the real layout lands)
    ry = top
    d.text((rx, ry), "E-INK CALIBRATION", font=font("Inter-SemiBold.otf", S(20)), fill=BLACK)
    ry += S(34)
    d.text((rx, ry), "16 gray levels — count the steps", font=small, fill=INK)
    ry += S(30)
    sw = right_w / 8
    for i in range(16):
        v = round(i * 255 / 15)
        cx, cy = rx + (i % 8) * sw, ry + (i // 8) * S(48)
        d.rectangle([cx, cy, cx + sw - S(3), cy + S(42)], fill=v, outline=BLACK if v > 230 else None)
    ry += S(110)
    d.text((rx, ry), "Line weights: 1 · 2 · 3 · 5 px", font=small, fill=INK)
    ry += S(30)
    for px in (1, 2, 3, 5):
        d.rectangle([rx, ry, rx + right_w, ry + px - 1], fill=BLACK)
        ry += S(22)
    ry += S(14)
    d.text((rx, ry), "Type ladder (Lora)", font=small, fill=INK)
    ry += S(30)
    for pt in (14, 18, 22, 28, 36):  # literal pixels: this is calibration
        d.text((rx, ry), f"{pt}px reads well?", font=lora(pt, 520), fill=BLACK)
        ry += pt + S(12)

    # Footer: the freshness stamp
    fy = h - S(96)
    d.rectangle([m, fy, w - m, fy + S(2)], fill=BLACK)
    fy += S(22)
    para(d, (m, fy), f"Printed {now.strftime('%d %b %Y, %H:%M')} IST · {w}×{h} · "
         "Edge to edge, no stretching = correct size.", small, col_w, S(26))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--size", default="1272x1696", help="WIDTHxHEIGHT (Paperwhite 12th gen framebuffer)")
    ap.add_argument("--test", action="store_true", help="render the static test page")
    args = ap.parse_args()
    w, h = map(int, args.size.lower().split("x"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    name = f"test_{w}x{h}.png" if args.test else "today.png"
    render(w, h, datetime.now(IST), test=args.test).save(out / name, optimize=True)
    print("wrote", out / name)


if __name__ == "__main__":
    main()
