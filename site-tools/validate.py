#!/usr/bin/env python3
"""Validate the generated site and preserve source scientific records."""
from pathlib import Path
from urllib.parse import urlsplit, unquote
from collections import Counter
import json
import sys
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / '_site'
PAGES = ['index.html','people.html','peirong-lin.html','current-research.html','research.html','publications.html','teaching.html','Resources.html','paper-radar.html','contact.html']
errors, warnings = [], []
parsed = {}
for filename in PAGES:
    path = SITE / filename
    if not path.exists():
        errors.append(f'Missing page: {filename}')
        continue
    soup = BeautifulSoup(path.read_text(), 'html.parser')
    parsed[filename] = soup
    if not soup.select_one('.gw-header nav'):
        errors.append(f'{filename}: missing static navigation')
    if not soup.select_one('.gw-skip') or not soup.find('main'):
        errors.append(f'{filename}: missing accessible main landmark')
    if len(soup.select('.gw-header nav a')) != 10:
        errors.append(f'{filename}: incomplete navigation')
    if soup.select_one('script[src*="assets/nav.js"], script[src*="assets/home-v2.js"]'):
        errors.append(f'{filename}: legacy runtime content mutation remains')
    if not soup.select_one('meta[name="geowater-build"]'):
        errors.append(f'{filename}: missing build identifier')
    ids = [node['id'] for node in soup.select('[id]')]
    duplicates = [key for key,count in Counter(ids).items() if count > 1]
    if duplicates:
        errors.append(f'{filename}: duplicate ids {duplicates}')
    for node in soup.select('script[src], img[src], link[rel="stylesheet"]'):
        value = node.get('src') or node.get('href')
        url = urlsplit(value)
        if url.scheme or url.netloc or value.startswith('data:'):
            continue
        target = SITE / unquote(url.path).lstrip('/')
        if not target.is_file():
            errors.append(f'{filename}: missing local asset {value}')

for filename, soup in parsed.items():
    for anchor in soup.select('a[href]'):
        href = anchor['href']
        url = urlsplit(href)
        if url.scheme or url.netloc or not href:
            continue
        destination = unquote(url.path).lstrip('/') or (filename if href.startswith('#') else 'index.html')
        target = SITE / destination
        if target.is_dir():
            target = target / 'index.html'
            destination = destination.rstrip('/') + '/index.html'
        if not target.exists():
            errors.append(f'{filename}: broken local link {href}')
            continue
        if url.fragment and target.suffix == '.html':
            target_soup = parsed.get(destination) or BeautifulSoup(target.read_text(), 'html.parser')
            if not target_soup.find(id=unquote(url.fragment)) and not target_soup.find(attrs={'name':unquote(url.fragment)}):
                errors.append(f'{filename}: missing anchor {href}')

source = BeautifulSoup((ROOT / 'publications.html').read_text(), 'html.parser')
source_titles = Counter(node.get_text(' ',strip=True) for node in source.select('.pub-item .pub-title'))
output_titles = Counter(node.get_text(' ',strip=True) for node in parsed['publications.html'].select('.publications-content .pub-item .pub-title'))
if source_titles != output_titles:
    errors.append('Scientific publication titles were dropped or changed')
source_authors = Counter(node.get_text(' ',strip=True) for node in source.select('.pub-item .pub-authors'))
output_authors = Counter(node.get_text(' ',strip=True) for node in parsed['publications.html'].select('.publications-content .pub-item .pub-authors'))
if source_authors != output_authors:
    errors.append('Publication authors were dropped or changed')
resources = parsed['Resources.html']
if resources.get_text().count('Data access forthcoming'):
    errors.append('Unresolved primary data placeholders')
if len(resources.select('.resource-card .gw-data-actions')) != 5:
    errors.append('Not all five data products have access actions')
for i in range(1,4):
    if not parsed['current-research.html'].find(id=f'question-{i}'):
        errors.append(f'Missing scientific question {i}')
if not (SITE / 'assets/geowater-icon.svg').exists():
    errors.append('Missing favicon')
result = {'pagesChecked':len(parsed), 'publicationRecordsPreserved':sum(source_titles.values()), 'errors':errors, 'warnings':warnings}
(ROOT / 'test-results').mkdir(exist_ok=True)
(ROOT / 'test-results/static-checks.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
sys.exit(1 if errors else 0)
