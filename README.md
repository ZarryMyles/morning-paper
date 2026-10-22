# The Mahanth Times 🗞️

A personal morning newspaper, printed on a jailbroken Kindle Paperwhite instead of paper.
Inspired by Karen X. Cheng's newspaper bot.

```
 GitHub Actions (04:53 IST)          GitHub                       Kindle
┌─────────────────────────┐   ┌────────────────────┐   ┌──────────────────────────┐
│ generator/render.py     │──▶│ "paper" branch     │◀──│ fetch.sh downloads and   │
│ renders today.png       │   │ today.png (1 commit│   │ draws it with FBInk/eips │
│ (1272×1696, grayscale)  │   │ force-pushed daily)│   │                          │
└─────────────────────────┘   └────────────────────┘   └──────────────────────────┘
```

## Layout

| Path | What it is |
|---|---|
| `generator/` | Python renderer + bundled fonts (Lora, Inter, DejaVu, all open licenses) |
| `.github/workflows/paper.yml` | Daily cron, manual button, and auto-run on generator changes |
| `kindle/morningpaper/` | Engine that lives at the Kindle's root (`/mnt/us/morningpaper`) |
| `kindle/documents/` | Scriptlets: they appear as "books" in the Kindle library |

## Render locally

```bash
pip install -r generator/requirements.txt
python generator/paper.py --out out --fixtures  # full edition from sample data (no network)
python generator/paper.py --out out             # full edition, live data
python generator/render.py --out out --test     # calibration test page
```

## Install on the Kindle (Paperwhite 12th gen, scriptlet jailbreak)

1. Plug the Kindle in over USB.
2. Copy `kindle/morningpaper/` to the **root** of the Kindle drive.
3. Copy `kindle/documents/*.sh` into the Kindle's **documents** folder.
4. **Private repo only:** create `morningpaper/paper.local.conf` on the Kindle with
   `GITHUB_TOKEN=github_pat_…` (fine-grained token: this repo only, *Contents: Read-only*).
5. Eject, then tap the **Morning Paper** books in your library:

| Scriptlet | Does |
|---|---|
| 1 – Device info | Writes `info.txt` (screen, firmware, tools) |
| 2 – Show test text | Draws `message.txt` |
| 3 – Show front page | Draws the bundled calibration page |
| 4 – Network test | Writes `net.txt` (HTTP/HTTPS checks) |
| 5 – Fetch & read today's paper | Downloads the edition and opens the page viewer (also saves a PDF copy to your library) |
| 6 – Touch probe | Records touchscreen info into `probe.txt` (diagnostics) |
| 7 – Read the paper (offline) | Re-opens the last downloaded edition in the viewer |

### Reading
Tap the right side (or swipe left) for the next page, tap the left 30% (or swipe right) to go back.
Tap on the last page to close; press and hold anywhere to close early. The viewer also closes after
10 idle minutes or when you press the power button.

Pages are drawn pixel-for-pixel by FBInk, so they're sharper than the PDF in the Kindle reader.
Touches come from `bin/tapread`, a tiny static ARM program ([source](kindle/src/tapread.c)) that
claims the touchscreen while the paper is open so taps don't reach the home screen underneath.
The kernel releases that claim automatically if it ever exits. Rebuild it with:

```bash
pip install ziglang
python -m ziglang cc -target arm-linux-musleabihf -static -Os -s -o kindle/morningpaper/bin/tapread kindle/src/tapread.c
```

Logs go to `morningpaper/log.txt`.

## Roadmap

- [x] Step 1: Kindle can draw an image, and fetch one from GitHub
- [x] Step 2: 11-page edition — weather, air quality, news, Hacker News, frontend, GitHub, on this day, word, quote, xkcd
- [x] Step 2½: pixel-perfect tap-to-turn viewer
- [ ] Step 3: automatic morning download + the cover as the sleep screen
