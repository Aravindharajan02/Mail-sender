#!/usr/bin/env python3
"""
find_mail.py - finds company / HR contact emails for a city, saves them to
receiveremailid.txt (the file send_job_mail.py reads).

100% free: OpenStreetMap (Nominatim + Overpass) to find companies in a city,
then reads each company's own public website for a published email.
Standard library only - nothing to install.

Run:   python find_mail.py
It asks: location (e.g. Chennai / Dubai / Singapore), how many emails,
and optionally an industry keyword.
"""

import csv
import json
import re
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path

BASE = Path(__file__).resolve().parent
RECEIVER_FILE = BASE / "receiveremailid.txt"
CSV_FILE = BASE / "companies_found.csv"
SENT_LOG = BASE / "sent_log.txt"

UA = "JobSeekerEmailFinder/1.0 (personal job search script)"
OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
NOMINATIM = "https://nominatim.openstreetmap.org/search"
DELAY = 2
PATHS = ["", "/careers", "/jobs", "/contact", "/contact-us", "/about", "/about-us"]
PREFERRED = ("career", "jobs", "hr", "recruit", "talent", "hiring", "people", "apply")
SKIP_PREFIX = ("noreply", "no-reply", "donotreply", "webmaster", "abuse", "privacy",
               "support", "sales", "press", "legal", "billing", "admin")
BAD_END = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# OSM office types (companies, IT, consulting, etc.)
OFFICE_TYPES = "company|it|consulting|telecommunication|employment_agency|research|engineer|financial|insurance|architect|logistics|software"


def http(url, data=None, timeout=60, limit=1_000_000):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(limit)


def geocode(place):
    q = urllib.parse.urlencode({"q": place, "format": "json", "limit": 1})
    res = json.loads(http(f"{NOMINATIM}?{q}"))
    if not res:
        raise SystemExit(f"Could not find location: {place}")
    s, n, w, e = res[0]["boundingbox"]  # south, north, west, east
    print(f"Location: {res[0]['display_name']}")
    return s, w, n, e  # Overpass order: south, west, north, east


def overpass_query(query):
    """Try each free Overpass server, with retries. Returns parsed JSON or None."""
    body = urllib.parse.urlencode({"data": query}).encode()
    for attempt in range(2):
        for server in OVERPASS_SERVERS:
            try:
                return json.loads(http(server, data=body, timeout=75, limit=30_000_000))
            except Exception:
                time.sleep(3)
        time.sleep(8)
    return None


def split_bbox(s, w, n, e, step=0.08, max_side=6):
    """Cut a big city box into small tiles so each query is light."""
    s, w, n, e = float(s), float(w), float(n), float(e)
    rows = min(max_side, max(1, round((n - s) / step)))
    cols = min(max_side, max(1, round((e - w) / step)))
    for r in range(rows):
        for c in range(cols):
            yield (s + (n - s) * r / rows, w + (e - w) * c / cols,
                   s + (n - s) * (r + 1) / rows, w + (e - w) * (c + 1) / cols)


def find_companies(place, keyword, want=500):
    s, w, n, e = geocode(place)
    kw = f'["name"~"{keyword}",i]' if keyword else ""
    tiles = list(split_bbox(s, w, n, e))
    print(f"Searching OpenStreetMap in {len(tiles)} small area(s)...")
    companies, seen = [], set()
    skip_office = ("government", "ngo", "diplomatic", "educational_institution",
                   "political_party", "religion", "association", "foundation")
    for i, (ts, tw, tn, te) in enumerate(tiles, 1):
        bbox = f"{ts:.5f},{tw:.5f},{tn:.5f},{te:.5f}"
        query = f"""
        [out:json][timeout:60];
        (
          nwr["office"]{kw}["website"]({bbox});
          nwr["office"]{kw}["contact:website"]({bbox});
          nwr["office"]{kw}["email"]({bbox});
          nwr["office"]{kw}["contact:email"]({bbox});
        );
        out tags;
        """
        data = overpass_query(query)
        if data is None:
            print(f"  area {i}/{len(tiles)}: server busy, skipped")
            continue
        for el in data.get("elements", []):
            t = el.get("tags", {})
            name = t.get("name")
            if not name or t.get("office") in skip_office:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            site = t.get("website") or t.get("contact:website") or ""
            email = t.get("email") or t.get("contact:email") or ""
            companies.append({"name": name, "site": site.strip(),
                              "osm_email": email.split(";")[0].strip()})
        print(f"  area {i}/{len(tiles)}: {len(companies)} companies so far")
        if len(companies) >= want:
            break
        time.sleep(2)
    # companies that already have an email in OSM first (no website scraping needed)
    companies.sort(key=lambda c: not c["osm_email"])
    print(f"Found {len(companies)} companies listed with a website/email.")
    return companies


def clean_html(html):
    html = html.replace("&#64;", "@").replace("%40", "@")
    html = re.sub(r"\s*[\[\(]\s*at\s*[\]\)]\s*", "@", html, flags=re.I)
    html = re.sub(r"\s*[\[\(]\s*dot\s*[\]\)]\s*", ".", html, flags=re.I)
    return html


def host_of(site):
    return urllib.parse.urlparse(site).netloc.lower().removeprefix("www.")


def scrape_email(site):
    if not site.startswith("http"):
        site = "https://" + site
    p = urllib.parse.urlparse(site)
    root, host = f"{p.scheme}://{p.netloc}", host_of(site)
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.set_url(root + "/robots.txt")
        rp.read()
    except Exception:
        pass
    found = []
    for path in PATHS:
        url = urllib.parse.urljoin(root, path)
        try:
            if not rp.can_fetch(UA, url):
                continue
            html = clean_html(http(url, timeout=15).decode("utf-8", errors="ignore"))
        except Exception:
            time.sleep(DELAY)
            continue
        for em in EMAIL_RE.findall(html):
            em = em.lower().rstrip(".")
            d = em.split("@")[1]
            if em.endswith(BAD_END) or em.split("@")[0].startswith(SKIP_PREFIX):
                continue
            if d == host or d.endswith("." + host) or host.endswith("." + d):
                if em not in found:
                    found.append(em)
        time.sleep(DELAY)
        if any(e.split("@")[0].startswith(PREFERRED) for e in found):
            break  # got an HR/careers address, no need to look further
    found.sort(key=lambda e: not e.split("@")[0].startswith(PREFERRED))
    return found[0] if found else ""


def load_existing():
    s = set()
    for f in (RECEIVER_FILE, SENT_LOG):
        if f.exists():
            s |= {x.strip().lower() for x in re.split(r"[,\n;]+", f.read_text(encoding="utf-8")) if x.strip()}
    return s


def main():
    place = input("Location (e.g. Chennai, Dubai, Singapore): ").strip()
    if not place:
        raise SystemExit("Location is required.")
    try:
        target = int(input("How many emails do you want? [50]: ").strip() or 50)
    except ValueError:
        target = 50
    keyword = input("Industry keyword in company name (optional, e.g. tech|soft|digital): ").strip()

    companies = find_companies(place, keyword, want=target * 12)
    existing = load_existing()
    results = []

    for c in companies:
        if len(results) >= target:
            break
        email = c["osm_email"].lower()
        if not email and c["site"]:
            print(f"Checking {c['name']} ({host_of(c['site'])})...")
            email = scrape_email(c["site"])
        if not EMAIL_RE.fullmatch(email or ""):
            continue
        if email in existing or any(r[1] == email for r in results):
            continue
        print(f"  + {email}")
        results.append([c["name"], email, c["site"], place])

    if not results:
        print("\nNo new emails found. Try another location, or leave the keyword blank.")
        return

    old = RECEIVER_FILE.read_text(encoding="utf-8").strip() if RECEIVER_FILE.exists() else ""
    new = "\n".join(r[1] for r in results)
    RECEIVER_FILE.write_text((old + "\n" + new).strip() + "\n", encoding="utf-8")

    new_csv = not CSV_FILE.exists()
    with CSV_FILE.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_csv:
            w.writerow(["company", "email", "website", "location"])
        w.writerows(results)

    print(f"\nSaved {len(results)} new emails to {RECEIVER_FILE.name} (details in {CSV_FILE.name}).")
    if len(results) < target:
        print(f"Only {len(results)} of {target} found - many companies publish no email. Try another area or keyword.")
    print("Open receiveremailid.txt and delete any address you don't want, then run send_job_mail.py.")


if __name__ == "__main__":
    main()
