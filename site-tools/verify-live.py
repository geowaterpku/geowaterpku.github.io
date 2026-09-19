#!/usr/bin/env python3
"""Confirm the public Pages deployment matches the generated release.

Only the lab's public website is requested. No credentials or visitor data are
read or transmitted. Query parameters avoid stale intermediary caches.
"""
from pathlib import Path
from urllib.request import Request, urlopen
import json
import time
from bs4 import BeautifulSoup

BASE = 'https://geowaterpku.github.io/'
EXPECTED = json.loads(Path('_site/build-info.json').read_text())['commit']
PAGES = ['index.html','people.html','peirong-lin.html','current-research.html','research.html','publications.html','teaching.html','Resources.html','paper-radar.html','contact.html']
SELECTORS = {'index.html':'#selected-research', 'publications.html':'#publication-search',
 'peirong-lin.html':'.gw-profile', 'current-research.html':'#question-1',
 'Resources.html':'.gw-data-actions', 'paper-radar.html':'#radar-search', 'contact.html':'.gw-contact-paths'}

def fetch(path):
    url = BASE + path + '?release=' + EXPECTED
    request = Request(url, headers={'Cache-Control':'no-cache', 'User-Agent':'GeoWater-Release-Verification/1.0'})
    with urlopen(request, timeout=12) as response:
        return response.read().decode('utf-8')

last_error = None
for attempt in range(1, 16):
    try:
        live = json.loads(fetch('build-info.json'))
        if live.get('commit') != EXPECTED:
            raise RuntimeError(f"Expected release {EXPECTED}; public build is {live.get('commit')}")
        checked = []
        for page in PAGES:
            soup = BeautifulSoup(fetch(page), 'html.parser')
            marker = soup.select_one('meta[name="geowater-build"]')
            if not marker or marker.get('content') != EXPECTED:
                raise RuntimeError(f'{page}: release marker mismatch')
            if len(soup.select('.gw-header nav a')) != 10:
                raise RuntimeError(f'{page}: incomplete public navigation')
            if page in SELECTORS and not soup.select_one(SELECTORS[page]):
                raise RuntimeError(f'{page}: expected feature not served')
            checked.append(page)
        result = {'status':'passed','publicRelease':EXPECTED,'pagesVerified':checked,'attempt':attempt}
        Path('test-results').mkdir(exist_ok=True)
        Path('test-results/live-verification.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result,indent=2))
        break
    except Exception as error:
        last_error = str(error)
        print(f'Public release check {attempt}/15: {last_error}', flush=True)
        if attempt == 15:
            raise SystemExit('Public deployment verification failed: ' + last_error)
        time.sleep(4)
