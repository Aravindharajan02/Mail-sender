#!/usr/bin/env python3
"""
Finds PUBLICLY LISTED contact emails on companies' own websites
(careers / contact / about pages). Free, standard library only.

Usage:
    1. Create companies.txt next to this script, one website per line:
           https://www.example.com
           https://www.anothercompany.com
    2. Run:  python find_company_emails.py
    3. Results are saved to found_emails.csv (company, email, page where found).

Notes:
  - Respects robots.txt and waits between requests.
  - Only keeps emails on the company's own domain.
  - Prefers careers/hr/jobs/recruit/talent addresses and puts them first.
  - Review the CSV by hand before mailing. Only mail addresses that are
    published for business/recruitment purposes.
"""

import csv
import re
import sys
import time
import urllib.request
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlparse

BASE = Path(__file__).resolve().parent
INPUT = BASE / "companies.txt"
OUTPUT = BASE / "found_emails.csv"

USER_AGENT = "Mozilla/5.0 (compatible; JobSeekerEmailFinder/1.0)"
DELAY = 3  # seconds between requests
PATHS = ["", "/careers", "/jobs", "/contact", "/contact-us", "/about", "/about-us", "/join-us"]
PREFERRED = ("career", "jobs", "hr", "recruit", "talent", "hiring", "people", "apply")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
BAD_END = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")


def can_fetch(rp, url):
    try:
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return True


def get_robots(root):
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.set_url(urljoin(root, "/robots.txt"))
        rp.read()
    except Exception:
        pass
    return rp


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as r:
        if "text/html" not in r.headers.get("Content-Type", ""):
            return ""
        return r.read(1_000_000).decode("utf-8", errors="ignore")


def clean_html(html):
    # decode common obfuscation: "name [at] company.com" / "(at)" / "&#64;"
    html = html.replace("&#64;", "@").replace("%40", "@")
    html = re.sub(r"\s*[\[\(]\s*at\s*[\]\)]\s*", "@", html, flags=re.I)
    html = re.sub(r"\s*[\[\(]\s*dot\s*[\]\)]\s*", ".", html, flags=re.I)
    return html


def base_domain(host):
    host = host.lower().removeprefix("www.")
    return host


def main():
    if not INPUT.exists():
        sys.exit(f"Create {INPUT.name} with one company website per line.")
    sites = [l.strip() for l in INPUT.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = []

    for site in sites:
        if not site.startswith("http"):
            site = "https://" + site
        host = base_domain(urlparse(site).netloc)
        root = f"{urlparse(site).scheme}://{urlparse(site).netloc}"
        print(f"\n{host}")
        rp = get_robots(root)
        found = {}

        for path in PATHS:
            url = urljoin(root, path)
            if not can_fetch(rp, url):
                continue
            try:
                html = clean_html(fetch(url))
            except Exception:
                time.sleep(DELAY)
                continue
            for email in EMAIL_RE.findall(html):
                email = email.lower().rstrip(".")
                if email.endswith(BAD_END):
                    continue
                domain = email.split("@")[1]
                if domain == host or domain.endswith("." + host) or host.endswith("." + domain):
                    found.setdefault(email, url)
            time.sleep(DELAY)

        ordered = sorted(found, key=lambda e: (not e.split("@")[0].startswith(PREFERRED), e))
        if not ordered:
            print("  no public email found (try LinkedIn / job portal instead)")
        for e in ordered:
            print(f"  {e}   <- {found[e]}")
            rows.append([host, e, found[e]])

    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["company", "email", "found_on"])
        w.writerows(rows)
    print(f"\nSaved {len(rows)} emails to {OUTPUT.name}")


if __name__ == "__main__":
    main()
