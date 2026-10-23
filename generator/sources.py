"""Data sources for The Myles Times. All free, no API keys.

Each fetch_* function returns plain data (dicts/lists) and may raise; the
caller wraps every source so one dead feed never stops the presses.
"""
import html
import os
import random
import re
from datetime import datetime, timedelta, timezone

import feedparser
import requests

IST = timezone(timedelta(hours=5, minutes=30))
LAT, LON = 13.0547, 77.6339          # Thanisandra, Bengaluru
UA = {"User-Agent": "MylesTimes/1.0 (personal e-ink newspaper; github.com/ZarryMyles/morning-paper)"}
TIMEOUT = 20


def get_json(url, **kw):
    headers = {**UA, **kw.pop("headers", {})}
    r = requests.get(url, headers=headers, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r.json()


# Characters our bundled fonts can draw: Latin, Greek, Cyrillic, general
# punctuation, super/subscripts and currency. Anything else (CJK, emoji...)
# would print as empty boxes on the page.
_DRAWABLE = re.compile(r"[^\u0000-\u052F\u1E00-\u1EFF\u2000-\u206F\u2070-\u20CF\u2100-\u214F]+")


def drawable(text):
    return re.sub(r"\s+", " ", _DRAWABLE.sub(" ", text or "")).strip(" -–—|:·")


def clean(text, limit=None):
    """Strip HTML tags/entities, undrawable characters, and squeeze whitespace."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = text.replace("₹", "Rs ")  # no bundled font has the rupee sign
    text = drawable(re.sub(r"\s+", " ", text))
    text = re.sub(r"\s+([.,;:!?)])", r"\1", text).strip()   # "War I ." -> "War I."
    if limit and len(text) > limit:
        text = text[: limit - 1].rsplit(" ", 1)[0] + "…"
    return text


# --- Weather & air -----------------------------------------------------------
WMO = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    56: "Freezing drizzle", 57: "Freezing drizzle", 61: "Light rain", 63: "Rain",
    65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain", 71: "Light snow",
    73: "Snow", 75: "Heavy snow", 77: "Snow grains", 80: "Light showers",
    81: "Showers", 82: "Violent showers", 85: "Snow showers", 86: "Snow showers",
    95: "Thunderstorm", 96: "Thunderstorm, hail", 99: "Thunderstorm, hail",
}


def fetch_weather():
    d = get_json("https://api.open-meteo.com/v1/forecast", params={
        "latitude": LAT, "longitude": LON, "timezone": "Asia/Kolkata", "forecast_days": 4,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
        "hourly": "temperature_2m,precipitation_probability,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
                 "precipitation_sum,sunrise,sunset,uv_index_max,wind_speed_10m_max",
    })
    cur, day, hr = d["current"], d["daily"], d["hourly"]
    today = day["time"][0]
    hourly = [
        {"hour": int(t[11:13]), "temp": hr["temperature_2m"][i], "rain": hr["precipitation_probability"][i]}
        for i, t in enumerate(hr["time"]) if t.startswith(today) and 6 <= int(t[11:13]) <= 23
    ]
    days = [{
        "date": day["time"][i], "code": day["weather_code"][i],
        "max": day["temperature_2m_max"][i], "min": day["temperature_2m_min"][i],
        "rain": day["precipitation_probability_max"][i], "rain_mm": day["precipitation_sum"][i],
    } for i in range(len(day["time"]))]
    return {
        "now_temp": cur["temperature_2m"], "feels": cur["apparent_temperature"],
        "humidity": cur["relative_humidity_2m"], "wind": cur["wind_speed_10m"],
        "code": day["weather_code"][0], "max": day["temperature_2m_max"][0],
        "min": day["temperature_2m_min"][0], "rain": day["precipitation_probability_max"][0],
        "rain_mm": day["precipitation_sum"][0], "uv": day["uv_index_max"][0],
        "wind_max": day["wind_speed_10m_max"][0],
        "sunrise": day["sunrise"][0][11:16], "sunset": day["sunset"][0][11:16],
        "hourly": hourly, "days": days,
    }


AQI_BANDS = [  # US AQI
    (50, "Good", "Air is clean. A great morning to be outdoors."),
    (100, "Moderate", "Fine for most. Very sensitive people may want an easier run."),
    (150, "Unhealthy for sensitive groups", "Asthma or heart concerns? Keep outdoor effort light."),
    (200, "Unhealthy", "Consider an indoor workout today."),
    (300, "Very unhealthy", "Limit time outdoors; a mask helps."),
    (999, "Hazardous", "Stay indoors if you can."),
]


def aqi_band(v):
    for limit, name, advice in AQI_BANDS:
        if v <= limit:
            return name, advice
    return AQI_BANDS[-1][1:]


def fetch_air():
    d = get_json("https://air-quality-api.open-meteo.com/v1/air-quality", params={
        "latitude": LAT, "longitude": LON, "timezone": "Asia/Kolkata", "forecast_days": 1,
        "current": "us_aqi,pm2_5,pm10,ozone,nitrogen_dioxide,carbon_monoxide",
        "hourly": "us_aqi",
    })
    cur = d["current"]
    hourly = [{"hour": int(t[11:13]), "aqi": v} for t, v in zip(d["hourly"]["time"], d["hourly"]["us_aqi"])
              if v is not None]
    name, advice = aqi_band(cur["us_aqi"])
    return {"aqi": cur["us_aqi"], "band": name, "advice": advice,
            "pm2_5": cur["pm2_5"], "pm10": cur["pm10"], "o3": cur["ozone"],
            "no2": cur["nitrogen_dioxide"], "co": cur["carbon_monoxide"], "hourly": hourly}


# --- Tech ----------------------------------------------------------------------
def domain(url):
    m = re.match(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1) if m else "news.ycombinator.com"


def fetch_hackernews(n=12):
    d = get_json("https://hn.algolia.com/api/v1/search", params={"tags": "front_page", "hitsPerPage": 30})
    hits = sorted(d["hits"], key=lambda h: h.get("points") or 0, reverse=True)[:n]
    return [{"title": h["title"], "site": domain(h.get("url")), "points": h.get("points") or 0,
             "comments": h.get("num_comments") or 0} for h in hits]


FRONTEND_FEEDS = [
    ("JavaScript Weekly", "https://cprss.s3.amazonaws.com/javascriptweekly.com.xml", 3),
    ("React", "https://react.dev/rss.xml", 2),
    ("Next.js", "https://nextjs.org/feed.xml", 2),
    ("Smashing Magazine", "https://www.smashingmagazine.com/feed/", 2),
    ("CSS-Tricks", "https://css-tricks.com/feed/", 2),
    ("web.dev", "https://web.dev/static/blog/feed.xml", 2),
]

NEWS_FEEDS = [
    ("Bengaluru", "https://www.thehindu.com/news/cities/bangalore/feeder/default.rss", 4),
    ("India", "https://www.thehindu.com/news/national/feeder/default.rss", 4),
    ("World", "https://feeds.bbci.co.uk/news/world/rss.xml", 4),
]


def strip_newsletter_header(text):
    """Cooperpress newsletters (JavaScript Weekly & co.) open every summary with
    "#807 — October 20, 2026 Read on the Web JavaScript Weekly". The exact
    characters vary (non-breaking spaces etc.), so cut by landmark instead."""
    m = re.search(r"Read on the Web", text[:120], re.I)
    if m:
        text = text[m.end():]
    else:  # no landmark: drop a leading "#807 — <date>" however it's spaced
        text = re.sub(r"^\W*#\s*\d+\W+[A-Za-z]+\W+\d{1,2}\W+\d{4}\W*", "", text)
    text = re.sub(r"^\W*(JavaScript|Node|Frontend|React|Golang|Ruby|Postgres) Weekly\W*", "", text, flags=re.I)
    return text.strip()


def entry_time(e):
    for key in ("published_parsed", "updated_parsed"):
        if e.get(key):
            return datetime(*e[key][:6], tzinfo=timezone.utc)
    return None


def fetch_feeds(feeds, max_age_days=None):
    """Returns [{"name", "items": [{"title", "summary", "age"}]}]; skips feeds that fail."""
    out, now = [], datetime.now(timezone.utc)
    for name, url, n in feeds:
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT)
            r.raise_for_status()
            parsed = feedparser.parse(r.content)
            items = []
            for e in parsed.entries:
                t = entry_time(e)
                if max_age_days and t and now - t > timedelta(days=max_age_days):
                    continue
                summary = clean(e.get("summary") or e.get("description"))
                summary = strip_newsletter_header(summary)
                if len(summary) > 220:
                    summary = summary[:219].rsplit(" ", 1)[0] + "…"
                items.append({"title": clean(e.get("title"), 140),
                              "summary": summary,
                              "date": t.astimezone(IST).strftime("%d %b") if t else ""})
                if len(items) >= n:
                    break
            if items:
                out.append({"name": name, "items": items})
        except Exception as exc:  # noqa: BLE001  one feed failing is fine
            print(f"  feed {name} failed: {exc}")
    if not out:
        raise RuntimeError("every feed failed")
    return out


def fetch_github_rising(n=8):
    """Most-starred repos created in the last 7 days (GitHub has no trending API)."""
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):  # Actions provides one; raises the rate limit
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    d = get_json("https://api.github.com/search/repositories", headers=headers,
                 params={"q": f"created:>{since}", "sort": "stars", "order": "desc", "per_page": n})
    def desc(raw):
        if not raw:
            return "No description."
        text = clean(raw, 150)
        return text if len(re.sub(r"[^A-Za-z]", "", text)) >= 8 else "(Description not in English.)"

    return [{"name": r["full_name"], "desc": desc(r.get("description")),
             "lang": r.get("language") or "—", "stars": r["stargazers_count"]} for r in d["items"]]


# --- Culture -------------------------------------------------------------------
def fetch_on_this_day(now, n=7):
    d = get_json(f"https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/selected/{now:%m}/{now:%d}")
    events = sorted(d.get("selected", []), key=lambda e: e.get("year", 0))
    if len(events) > n:  # spread picks across history rather than taking the first n
        step = len(events) / n
        events = [events[int(i * step)] for i in range(n)]
    return [{"year": e["year"], "text": clean(e["text"], 260)} for e in events]


def fetch_quote():
    d = get_json("https://zenquotes.io/api/today")[0]
    return {"quote": clean(d["q"]), "author": clean(d["a"])}


def fetch_word():
    feed = feedparser.parse(requests.get(
        "https://en.wiktionary.org/w/api.php",
        params={"action": "featuredfeed", "feed": "wotd", "feedformat": "atom"},
        headers=UA, timeout=TIMEOUT).content)
    e = feed.entries[-1]  # newest last
    body = e.get("summary") or ""
    word = clean(re.search(r"<b>(.*?)</b>|<strong>(.*?)</strong>", body).group(0)) if re.search(r"<b>|<strong>", body) \
        else clean(e.title.split(":")[-1])
    pos_m = re.search(r"<i>(noun|verb|adjective|adverb|interjection|preposition|pronoun|conjunction|phrase|proper noun)[^<]*</i>",
                      body, re.I)
    junk = re.compile(r"word of the day|nominate|archive|suggest|wiktionary|feedback", re.I)
    defs = [clean(li, 300) for li in re.findall(r"<li[^>]*>(.*?)</li>", body, re.S)]
    defs = [x for x in defs if len(x) > 3 and not junk.search(x)][:4]
    return {"word": word, "pos": pos_m.group(1).lower() if pos_m else "",
            "definitions": defs or [clean(body, 400)]}


# --- Comics ----------------------------------------------------------------------
def fetch_xkcd(now):
    latest = get_json("https://xkcd.com/info.0.json")
    # New strips land Mon/Wed/Fri. Other days get a random classic, stable for the day.
    if now.weekday() in (0, 2, 4):
        strip, label = latest, "Latest strip"
    else:
        rng = random.Random(now.strftime("%Y%m%d"))
        num = rng.randint(1, latest["num"] - 1)
        while num == 404:  # the famous missing one
            num = rng.randint(1, latest["num"] - 1)
        strip, label = get_json(f"https://xkcd.com/{num}/info.0.json"), "From the archive"
    # Newer strips have a 2x version: much crisper on a 300 ppi screen.
    img = None
    if strip["img"].endswith(".png"):
        r = requests.get(strip["img"][:-4] + "_2x.png", headers=UA, timeout=TIMEOUT)
        if r.ok and r.content[:4] == b"\x89PNG":
            img = r.content
    if img is None:
        r = requests.get(strip["img"], headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        img = r.content
    return {"num": strip["num"], "title": strip["safe_title"], "alt": strip["alt"],
            "image": img, "label": label}


# --- Wikipedia: featured article + picture of the day (one request) ------------------
_feed_cache = {}


def _featured_feed(now):
    key = now.strftime("%Y/%m/%d")
    if key not in _feed_cache:
        _feed_cache[key] = get_json(f"https://api.wikimedia.org/feed/v1/wikipedia/en/featured/{key}")
    return _feed_cache[key]


def fetch_featured_article(now):
    tfa = _featured_feed(now)["tfa"]
    title = tfa["titles"]["normalized"]
    # The feed's extract is a teaser; the article's lead section makes a real long read.
    paras = []
    try:
        d = get_json("https://en.wikipedia.org/w/api.php", params={
            "action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1,
            "titles": title, "format": "json", "formatversion": 2})
        lead = d["query"]["pages"][0].get("extract", "")
        paras = [clean(x) for x in lead.split("\n") if len(x.strip()) > 40]
    except Exception as exc:  # noqa: BLE001
        print(f"  lead section failed ({exc}); using the feed's summary")
    if not paras:
        paras = [clean(tfa.get("extract", ""))]
    return {"title": title, "description": clean(tfa.get("description", "")), "paragraphs": paras[:8]}


def fetch_picture(now):
    pic = _featured_feed(now)["image"]
    # Ask Commons for a ~1200px rendition rather than the (often huge) original.
    thumb = pic["thumbnail"]["source"]
    url = re.sub(r"/(\d+)px-", "/1200px-", thumb) if "/thumb/" in thumb else thumb
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    if not r.ok:
        r = requests.get(thumb, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    title = re.sub(r"^File:|\.[a-zA-Z]{3,4}$", "", pic.get("title", "")).replace("_", " ")
    return {"image": r.content, "title": clean(title, 90),
            "caption": clean((pic.get("description") or {}).get("text", ""), 420),
            "artist": clean((pic.get("artist") or {}).get("text", ""), 80),
            "license": (pic.get("license") or {}).get("type", "")}


# --- Money: the rupee against major currencies (ECB reference rates, weekdays) -------
CURRENCIES = [  # (code, name, units shown) -- all on the ECB's reference list
    ("USD", "US dollar", 1), ("EUR", "Euro", 1), ("GBP", "British pound", 1),
    ("JPY", "Japanese yen", 100), ("AUD", "Australian dollar", 1), ("CAD", "Canadian dollar", 1),
    ("SGD", "Singapore dollar", 1), ("CHF", "Swiss franc", 1), ("CNY", "Chinese yuan", 1),
    ("HKD", "Hong Kong dollar", 1),
]


def fetch_rupee(now):
    """One request with the rupee as base: returns foreign-per-rupee, flipped to rupees-per-unit."""
    start = (now - timedelta(days=16)).strftime("%Y-%m-%d")
    symbols = ",".join(c for c, _, _ in CURRENCIES)
    last_exc = None
    for base in ("https://api.frankfurter.dev/v1", "https://api.frankfurter.app"):
        try:
            d = get_json(f"{base}/{start}..", params={"base": "INR", "symbols": symbols})
            days = sorted(d["rates"].items())
            out = []
            for code, name, units in CURRENCIES:
                series = [(day, units / v[code]) for day, v in days if v.get(code)]
                if len(series) >= 2:
                    out.append({"code": code, "name": name, "units": units, "series": series[-8:],
                                "rate": series[-1][1], "prev": series[-2][1]})
            if out:
                return {"date": days[-1][0], "currencies": out}
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    raise RuntimeError(f"no rupee rates ({last_exc})")


SOURCES = {
    "weather": lambda now: fetch_weather(),
    "air": lambda now: fetch_air(),
    "hackernews": lambda now: fetch_hackernews(),
    "frontend": lambda now: fetch_feeds(FRONTEND_FEEDS, max_age_days=21),
    "github": lambda now: fetch_github_rising(),
    "news": lambda now: fetch_feeds(NEWS_FEEDS, max_age_days=2),
    "onthisday": fetch_on_this_day,
    "quote": lambda now: fetch_quote(),
    "word": lambda now: fetch_word(),
    "comic": fetch_xkcd,
    "article": fetch_featured_article,
    "picture": fetch_picture,
    "money": fetch_rupee,
}


def fetch_all(now):
    data, status = {}, {}
    for key, fn in SOURCES.items():
        try:
            data[key] = fn(now)
            status[key] = "ok"
            print(f"✓ {key}")
        except Exception as exc:  # noqa: BLE001
            data[key] = None
            status[key] = f"failed: {type(exc).__name__}: {exc}"[:300]
            print(f"✗ {key}: {exc}")
    return data, status
