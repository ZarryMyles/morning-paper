# The Myles Times 🗞️

A personal morning newspaper, printed on a jailbroken Kindle Paperwhite instead of paper.
Inspired by Karen X. Cheng's newspaper bot.

```
 GitHub Actions (03:12 + 04:42 IST)  GitHub                       Kindle
┌─────────────────────────┐   ┌────────────────────┐   ┌──────────────────────────┐
│ generator/paper.py      │──▶│ "paper" branch     │◀──│ fetch.sh downloads it,   │
│ renders 14 pages + PDF  │   │ one commit,        │   │ viewer.sh draws pages    │
│ (1272×1696, grayscale)  │   │ force-pushed daily │   │ pixel-for-pixel (FBInk)  │
└─────────────────────────┘   └────────────────────┘   └──────────────────────────┘
```

## Layout

| Path | What it is |
|---|---|
| `generator/` | Python renderer + bundled fonts: Chomsky (masthead), Old Standard (headlines), Libre Caslon (body), Libre Franklin (labels); all SIL OFL, licenses in `generator/fonts/licenses/` |
| `.github/workflows/paper.yml` | Daily cron, manual button, and auto-run on generator changes |
| `kindle/morningpaper/` | Engine that lives at the Kindle's root (`/mnt/us/morningpaper`) |
| `kindle/documents/` | The launcher scriptlet: appears as a "book" in the Kindle library |
| `kindle/src/` | Source for `tapread`, the touchscreen helper |

## Render locally

```bash
pip install -r generator/requirements.txt
python generator/paper.py --out out --fixtures  # full edition from sample data (no network)
python generator/paper.py --out out             # full edition, live data
```

## Install on the Kindle (Paperwhite 12th gen, scriptlet jailbreak)

1. Plug the Kindle in over USB.
2. Copy `kindle/morningpaper/` to the **root** of the Kindle drive.
3. Copy `kindle/documents/the_myles_times.sh` into the Kindle's **documents** folder.
4. **Private repo only:** create `morningpaper/paper.local.conf` on the Kindle with
   `GITHUB_TOKEN=github_pat_…` (fine-grained token: this repo only, *Contents: Read-only*).
5. Eject, then tap **The Myles Times** in your library. If today's edition is already on the
   Kindle it opens straight away; otherwise it downloads it first (offline, it opens the last
   edition you downloaded). A PDF copy is also saved to your library.

### Reading
Tap the right side (or swipe left) for the next page, tap the left 30% (or swipe right) to go back.
On the front page, tap an entry under **Inside** (or Rupee Watch) to jump straight to it.
Tap on the last page to close; press and hold anywhere to close early. The viewer also closes after
10 idle minutes or when you press the power button.

### The morning paper
Tapping the book also starts `bin/paperd.sh`, a small daemon that runs until the Kindle restarts:

- When the Kindle goes to sleep, it draws today's front page over the sleep screen.
- Before the Kindle suspends, it sets the real-time-clock alarm for `WAKE_TIME` (default 05:30).
- When the alarm wakes the Kindle, it turns Wi-Fi on, downloads the new edition, draws its front
  page, and turns Wi-Fi back off if it was off. If GitHub hasn't printed yet, it retries every
  20 minutes for 4 hours (GitHub's scheduled runs can start hours late).

Change `WAKE_TIME` or set `AUTO_FETCH=0` in `paper.conf`. After a restart, tap the book once to
start the daemon again.

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
- [x] Step 2: 14-page edition — weather + almanac, air quality, news, the rupee, Hacker News, frontend, GitHub, featured article, halftone picture of the day, on this day, word, quote, xkcd
- [x] Step 2½: pixel-perfect tap-to-turn viewer
- [x] Step 3: automatic morning download + the front page as the sleep screen
- [x] Tap the index to jump to a page
