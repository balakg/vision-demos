#!/usr/bin/env python3
"""
Scrape CVPR (CVF Open Access) and NeurIPS (papers.nips.cc) paper titles
and save lowercase title arrays to titles_data.json / titles_data.js.

Usage:
  python3 build_data.py              # full rebuild (2013–present)
  python3 build_data.py 2027         # add/refresh a single year
  python3 build_data.py 2026 2027    # add/refresh a range of years
"""

import json, os, re, sys, time
from urllib.request import urlopen, Request
from html.parser import HTMLParser

FIRST_YEAR = 2013
HERE = os.path.dirname(os.path.abspath(__file__))
JSON_OUT = os.path.join(HERE, "titles_data.json")
JS_OUT   = os.path.join(HERE, "titles_data.js")

# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch(url, retries=3):
    headers = {'User-Agent': 'Mozilla/5.0 (research data collection)'}
    for attempt in range(retries):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=20) as r:
                return r.read().decode('utf-8', errors='replace')
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  FAILED: {url} — {e}", file=sys.stderr)
                return None

# ── CVF / CVPR ────────────────────────────────────────────────────────────────

class CVFParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.titles = []; self._in = False
    def handle_starttag(self, tag, attrs):
        if tag == 'dt' and 'ptitle' in dict(attrs).get('class', ''):
            self._in = True
    def handle_endtag(self, tag):
        if tag == 'dt': self._in = False
    def handle_data(self, data):
        if self._in and data.strip(): self.titles.append(data.strip())

def scrape_cvpr(year):
    base = f"https://openaccess.thecvf.com/CVPR{year}"
    html = fetch(base + "?day=all")
    p = CVFParser()
    if html: p.feed(html)
    if p.titles:
        print(f"  CVPR {year}: {len(p.titles)} papers"); return p.titles
    html_main = fetch(base)
    titles = []
    if html_main:
        days = sorted(set(re.findall(r'day=(\d{4}-\d{2}-\d{2})', html_main)))
        if days:
            print(f"  CVPR {year}: fetching {len(days)} day pages")
            for day in days:
                dh = fetch(f"{base}?day={day}")
                if dh:
                    dp = CVFParser(); dp.feed(dh); titles += dp.titles
                time.sleep(0.3)
        else:
            p2 = CVFParser(); p2.feed(html_main); titles = p2.titles
    print(f"  CVPR {year}: {len(titles)} papers"); return titles

# ── NeurIPS ───────────────────────────────────────────────────────────────────

def scrape_neurips(year):
    for url in [f"https://papers.nips.cc/paper_files/paper/{year}",
                f"https://papers.nips.cc/paper/{year}"]:
        html = fetch(url)
        if not html: continue
        found = re.findall(r'href="/paper[^"]*"\s*>([^<]+)<', html)
        found = [t.strip() for t in found if len(t.strip()) > 10
                 and not t.strip().lower().startswith('submit')]
        if found:
            print(f"  NeurIPS {year}: {len(found)} papers"); return found
    print(f"  NeurIPS {year}: not available"); return None

# ── Save ──────────────────────────────────────────────────────────────────────

def save(data):
    with open(JSON_OUT, "w") as f:
        json.dump(data, f, separators=(',', ':'))
    with open(JS_OUT, "w") as f:
        f.write("const TITLES_DATA = ")
        json.dump(data, f, separators=(',', ':'))
        f.write(";\n")
    print(f"\nSaved ({os.path.getsize(JSON_OUT)//1024} KB)")

# ── Main ──────────────────────────────────────────────────────────────────────

args = sys.argv[1:]
if args:
    years = list(range(int(args[0]), int(args[-1]) + 1))
else:
    import datetime
    years = list(range(FIRST_YEAR, datetime.date.today().year + 1))

# Load existing data if updating specific years
if args and os.path.exists(JSON_OUT):
    with open(JSON_OUT) as f:
        data = json.load(f)
    print(f"Loaded existing data, updating years: {years}")
else:
    data = {"cvpr": {}, "neurips": {}}
    print(f"Full rebuild for years: {years}")

print("\n=== CVPR ===")
for year in years:
    titles = scrape_cvpr(year)
    data["cvpr"][str(year)] = [t.lower() for t in titles]
    time.sleep(0.5)

print("\n=== NeurIPS ===")
for year in years:
    titles = scrape_neurips(year)
    data["neurips"][str(year)] = [t.lower() for t in titles] if titles else None
    time.sleep(0.5)

print("\n=== Paper counts ===")
for conf in data:
    counts = {yr: (len(data[conf][yr]) if data[conf][yr] else "N/A")
              for yr in sorted(data[conf])}
    print(f"{conf}: {counts}")

save(data)
