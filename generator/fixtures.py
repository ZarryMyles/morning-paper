"""Sample data for designing pages offline (python generator/paper.py --fixtures).

Deliberately long-winded in places: worst-case text catches overflow bugs.
"""
import io

from PIL import Image, ImageDraw


def _fake_comic():
    """A stand-in stick-figure strip (the real paper prints xkcd)."""
    w, h = 1480, 520
    im = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(im)
    for i in range(3):
        x0 = 20 + i * 485
        d.rectangle([x0, 20, x0 + 460, h - 20], outline=0, width=4)
        cx, cy = x0 + 230, 250
        d.ellipse([cx - 28, cy - 120, cx + 28, cy - 64], outline=0, width=4)
        d.line([cx, cy - 64, cx, cy + 60], fill=0, width=4)
        d.line([cx, cy - 20, cx - 60, cy + 20 - i * 30], fill=0, width=4)
        d.line([cx, cy - 20, cx + 60, cy + 20], fill=0, width=4)
        d.line([cx, cy + 60, cx - 45, cy + 160], fill=0, width=4)
        d.line([cx, cy + 60, cx + 45, cy + 160], fill=0, width=4)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def sample_data():
    hourly = [{"hour": h, "temp": t, "rain": r} for h, t, r in zip(
        range(6, 24),
        [19.8, 20.4, 22.1, 24.0, 25.6, 26.9, 27.8, 28.3, 28.1, 27.2, 26.0, 24.6, 23.5, 22.6, 21.9, 21.3, 20.9, 20.6],
        [5, 5, 3, 3, 5, 10, 18, 35, 52, 64, 58, 40, 22, 12, 8, 5, 5, 3])]
    return {
        "weather": {
            "now_temp": 20.6, "feels": 20.9, "humidity": 88, "wind": 9.4, "code": 80,
            "max": 28.3, "min": 19.6, "rain": 64, "rain_mm": 4.2, "uv": 7.4, "wind_max": 16.2,
            "sunrise": "06:09", "sunset": "17:58", "hourly": hourly,
            "days": [
                {"date": "2026-10-23", "code": 80, "max": 28.3, "min": 19.6, "rain": 64, "rain_mm": 4.2},
                {"date": "2026-10-24", "code": 3, "max": 27.1, "min": 19.2, "rain": 30, "rain_mm": 0.8},
                {"date": "2026-10-25", "code": 95, "max": 26.4, "min": 19.0, "rain": 78, "rain_mm": 11.5},
                {"date": "2026-10-26", "code": 2, "max": 27.9, "min": 18.8, "rain": 15, "rain_mm": 0.0},
            ],
        },
        "air": {
            "aqi": 78, "band": "Moderate",
            "advice": "Fine for most. Very sensitive people may want an easier run.",
            "pm2_5": 24.6, "pm10": 51.3, "o3": 61.0, "no2": 28.4, "co": 410.0,
            "hourly": [{"hour": h, "aqi": a} for h, a in zip(range(24),
                       [92, 95, 97, 96, 94, 90, 86, 84, 82, 78, 72, 66, 61, 58, 57, 59, 63, 70, 79, 86, 90, 93, 94, 95])],
        },
        "hackernews": [
            {"title": "Show HN: I replaced my phone alarm with an e-ink newspaper my Kindle fetches at dawn",
             "site": "github.com", "points": 812, "comments": 241},
            {"title": "The surprising physics of electrophoretic displays, and why ghosting happens",
             "site": "eink-research.org", "points": 655, "comments": 120},
            {"title": "SQLite is not a toy database", "site": "antonz.org", "points": 590, "comments": 302},
            {"title": "React Compiler is now stable", "site": "react.dev", "points": 544, "comments": 288},
            {"title": "A visual guide to how CSS anchor positioning actually works under the hood",
             "site": "developer.chrome.com", "points": 430, "comments": 76},
            {"title": "Ask HN: What's a small tool you built that you use every day?",
             "site": "news.ycombinator.com", "points": 401, "comments": 517},
            {"title": "Postgres 19 released", "site": "postgresql.org", "points": 377, "comments": 140},
            {"title": "Why your monorepo build is slow (and how we cut ours from 40 to 4 minutes)",
             "site": "engineering.example.com", "points": 333, "comments": 98},
            {"title": "The bus factor of open source maintainers, measured",
             "site": "arxiv.org", "points": 290, "comments": 112},
            {"title": "I built a mechanical keyboard from scratch, including the PCB",
             "site": "blog.example.dev", "points": 260, "comments": 64},
            {"title": "Bengaluru's new metro line, by the numbers", "site": "thehindu.com", "points": 212, "comments": 88},
            {"title": "TypeScript 6.1 adds pattern matching", "site": "devblogs.microsoft.com", "points": 198, "comments": 153},
        ],
        "frontend": [
            {"name": "JavaScript Weekly", "items": [
                {"title": "The state of JavaScript runtimes in late 2026", "date": "21 Oct",
                 "summary": "Node, Deno and Bun keep converging on web-standard APIs; here is what that means for library authors shipping one package everywhere."},
                {"title": "Signals proposal reaches stage 3", "date": "20 Oct",
                 "summary": "A native reactive primitive for JavaScript moves closer to browsers, with frameworks already experimenting with interop."},
                {"title": "Temporal ships in every major browser", "date": "18 Oct", "summary": "Date handling finally gets the API it deserved."},
            ]},
            {"name": "React", "items": [
                {"title": "React 20: Activity and View Transitions", "date": "16 Oct",
                 "summary": "Keep offscreen UI alive cheaply and animate between routes with a single component."},
            ]},
            {"name": "Next.js", "items": [
                {"title": "Next.js 17", "date": "19 Oct",
                 "summary": "Turbopack builds by default, a new caching model, and smaller client bundles for server-heavy apps."},
                {"title": "Partial prerendering is stable", "date": "08 Oct", "summary": "Static shells with streaming dynamic holes."},
            ]},
            {"name": "Smashing Magazine", "items": [
                {"title": "Designing accessible data tables that survive mobile", "date": "20 Oct",
                 "summary": "Patterns for responsive tables that keep screen-reader semantics intact."},
            ]},
        ],
        "github": [
            {"name": "acme/ink-dash", "desc": "Turn any old e-reader into a low-power dashboard. Rust + FBInk.",
             "lang": "Rust", "stars": 4821},
            {"name": "someone/tiny-llm-router", "desc": "Route prompts across local and hosted models with a 200-line config.",
             "lang": "TypeScript", "stars": 3310},
            {"name": "devtools/fastgrep", "desc": "A grep that understands your monorepo's ignore rules and is very, very fast.",
             "lang": "Go", "stars": 2754},
            {"name": "css-wizard/anchor-kit", "desc": "Tooltips, popovers and menus built on CSS anchor positioning. Zero JS.",
             "lang": "CSS", "stars": 1980},
            {"name": "data/duck-notebooks", "desc": "Notebooks that run DuckDB in the browser.",
             "lang": "Python", "stars": 1544},
            {"name": "ui/radix-motion", "desc": "Motion primitives that compose with Radix UI.", "lang": "TypeScript", "stars": 1302},
            {"name": "infra/one-click-preview", "desc": "Preview deployments for any repo using only GitHub Actions.",
             "lang": "Shell", "stars": 1187},
            {"name": "games/terminal-cricket", "desc": "Ball-by-ball cricket in your terminal.", "lang": "Python", "stars": 965},
        ],
        "news": [
            {"name": "Bengaluru", "items": [
                {"title": "Yellow Line metro extends late-night service on weekends", "date": "22 Oct",
                 "summary": "BMRCL says trains will run until midnight on Fridays and Saturdays from November."},
                {"title": "Heavy rain alert for Bengaluru Urban over the next two days", "date": "22 Oct",
                 "summary": "IMD issues a yellow alert; waterlogging expected at underpasses in the north and east."},
                {"title": "Thanisandra Main Road widening to begin next month", "date": "21 Oct",
                 "summary": "Traffic diversions planned near Hegde Nagar during the works."},
                {"title": "Lalbagh flower show dates announced", "date": "21 Oct", "summary": ""},
            ]},
            {"name": "India", "items": [
                {"title": "Monsoon withdraws from most of the country, says IMD", "date": "22 Oct",
                 "summary": "The northeast monsoon is expected to set in over Tamil Nadu and coastal Andhra next week."},
                {"title": "UPI crosses 20 billion monthly transactions", "date": "22 Oct",
                 "summary": "NPCI data shows continued growth in small-ticket payments."},
                {"title": "New semiconductor fab announced in Gujarat", "date": "21 Oct", "summary": ""},
            ]},
            {"name": "World", "items": [
                {"title": "Global climate talks open with focus on adaptation funding", "date": "22 Oct",
                 "summary": "Delegates from nearly 200 countries meet as a new report warns of rising costs."},
                {"title": "Scientists map the most detailed model yet of the human brain", "date": "22 Oct",
                 "summary": "The connectome covers a cubic millimetre of cortex at synaptic resolution."},
                {"title": "Record numbers watch annular eclipse across South America", "date": "21 Oct", "summary": ""},
            ]},
        ],
        "onthisday": [
            {"year": 1797, "text": "André-Jacques Garnerin made the first recorded parachute jump, from a hydrogen balloon above Paris."},
            {"year": 1836, "text": "Sam Houston was inaugurated as the first president of the Republic of Texas."},
            {"year": 1879, "text": "Thomas Edison tested his first practical electric light bulb, which lasted over thirteen hours."},
            {"year": 1938, "text": "Chester Carlson made the first xerographic copy, the foundation of the photocopier."},
            {"year": 1962, "text": "President Kennedy announced the discovery of Soviet missiles in Cuba and a naval quarantine of the island."},
            {"year": 2001, "text": "Apple announced the iPod, a portable music player holding a thousand songs."},
            {"year": 2019, "text": "Google claimed quantum supremacy with its 53-qubit Sycamore processor."},
        ],
        "quote": {"quote": "The secret of getting ahead is getting started. The secret of getting started is "
                           "breaking your complex overwhelming tasks into small manageable tasks, and then starting on the first one.",
                  "author": "Mark Twain"},
        "word": {"word": "sesquipedalian", "pos": "adjective",
                 "definitions": [
                     "(of a word) Long; having many syllables.",
                     "(of a person or their writing) Given to using long words; long-winded, verbose.",
                     "(rare) Measuring a foot and a half in length.",
                 ]},
        "comic": {"num": 1234, "title": "Morning Routine", "label": "From the archive",
                  "alt": "I tried replacing my phone with a newspaper, but now I doomscroll the classifieds.",
                  "image": _fake_comic()},
    }
