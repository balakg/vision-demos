#!/usr/bin/env python3
"""
Scrape CVPR (CVF Open Access) and NeurIPS (papers.nips.cc) paper titles,
count per-word frequencies per year, and save to titles_data.json.
"""

import json, re, time, sys
from collections import defaultdict
from urllib.request import urlopen, Request
from urllib.error import URLError
from html.parser import HTMLParser

YEARS = list(range(2013, 2025))
STOP = {
    'a','an','the','of','for','in','on','at','to','with','from','by','and','or',
    'is','are','was','were','be','been','as','via','into','its','our','their',
    'this','that','using','based','toward','towards','learning','deep','neural',
}

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

def tokenize(title):
    words = re.findall(r"[a-z0-9][a-z0-9\-']*[a-z0-9]|[a-z0-9]", title.lower())
    return [w for w in words if len(w) > 1 and w not in STOP]

# ── CVF / CVPR ─────────────────────────────────────────────────────────────────

class CVFParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.titles = []
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == 'dt':
            classes = dict(attrs).get('class', '')
            if 'ptitle' in classes:
                self._in_title = True

    def handle_endtag(self, tag):
        if tag == 'dt':
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            t = data.strip()
            if t:
                self.titles.append(t)

def parse_cvf_titles(html):
    parser = CVFParser()
    parser.feed(html)
    return parser.titles

def scrape_cvpr(year):
    base = f"https://openaccess.thecvf.com/CVPR{year}"
    # Try ?day=all first
    html = fetch(base + "?day=all")
    titles = parse_cvf_titles(html) if html else []
    if titles:
        print(f"  CVPR {year}: {len(titles)} papers (all-days page)")
        return titles
    # Some years list individual days — discover them from the main page
    html_main = fetch(base)
    if html_main:
        days = list(set(re.findall(r'day=(\d{4}-\d{2}-\d{2})', html_main)))
        if days:
            print(f"  CVPR {year}: fetching {len(days)} day pages")
            for day in sorted(days):
                day_html = fetch(f"{base}?day={day}")
                if day_html:
                    titles += parse_cvf_titles(day_html)
                time.sleep(0.3)
        else:
            titles = parse_cvf_titles(html_main)
    print(f"    → {len(titles)} papers")
    return titles

# ── NeurIPS ────────────────────────────────────────────────────────────────────

def scrape_neurips(year):
    urls = [
        f"https://papers.nips.cc/paper_files/paper/{year}",
        f"https://papers.nips.cc/paper/{year}",
    ]
    titles = []
    for url in urls:
        print(f"  NeurIPS {year}: {url}")
        html = fetch(url)
        if not html:
            continue
        # Titles are in <a> tags inside <li> inside a <ul> with class "paper-list",
        # or plain <li><a href="/paper/...">TITLE</a></li> patterns.
        found = re.findall(r'href="/paper[^"]*"\s*>([^<]+)<', html)
        if not found:
            found = re.findall(r'href="/paper_files/paper[^"]*"\s*>([^<]+)<', html)
        # Filter out nav/UI strings
        found = [t.strip() for t in found if len(t.strip()) > 10 and not t.strip().lower().startswith('submit')]
        if found:
            titles = found
            break
    print(f"    → {len(titles)} papers")
    return titles

# ── Build dataset ──────────────────────────────────────────────────────────────
# Store lowercase titles as arrays — the HTML does client-side substring search.

data = {"cvpr": {}, "neurips": {}}

print("=== CVPR ===")
for year in YEARS:
    titles = scrape_cvpr(year)
    data["cvpr"][str(year)] = [t.lower() for t in titles]
    time.sleep(0.5)

print("\n=== NeurIPS ===")
for year in YEARS:
    titles = scrape_neurips(year)
    data["neurips"][str(year)] = [t.lower() for t in titles]
    time.sleep(0.5)

# Save
out = "/Users/guha/Desktop/vision-demos/paper-trends/titles_data.json"
with open(out, "w") as f:
    json.dump(data, f, separators=(',', ':'))

print("\n=== Paper counts ===")
for conf in data:
    counts = {yr: len(data[conf][yr]) for yr in data[conf]}
    print(f"{conf}: {counts}")

import os
print(f"\nSaved to {out} ({os.path.getsize(out)//1024} KB)")
