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
| 5 – Fetch today's paper | Saves today's PDF edition to your library and shows the cover |
| 6 – Touch probe | Records touchscreen info into `probe.txt` (for the tap-to-turn viewer) |

Logs go to `morningpaper/log.txt`.

## Roadmap

- [x] Step 1: Kindle can draw an image, and fetch one from GitHub
- [x] Step 2: 11-page edition — weather, air quality, news, Hacker News, frontend, GitHub, on this day, word, quote, xkcd
- [ ] Step 3: real front page and automatic morning refresh on the Kindle
