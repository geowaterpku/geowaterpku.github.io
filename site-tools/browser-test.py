#!/usr/bin/env python3
"""Browser regression checks against the built site on a local HTTP server."""
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread
import json
import sys
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / '_site'
RESULTS = ROOT / 'test-results'
RESULTS.mkdir(exist_ok=True)
PAGES = ['index.html','people.html','peirong-lin.html','current-research.html','research.html','publications.html','teaching.html','Resources.html','paper-radar.html','contact.html']
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass
server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(SITE)))
Thread(target=server.serve_forever, daemon=True).start()
BASE = f'http://127.0.0.1:{server.server_port}'
report = {'viewports':[], 'interactions':[], 'failures':[]}
def check(condition, label, detail=None):
    report['interactions'].append({'check':label,'passed':bool(condition)})
    if not condition:
        report['failures'].append({'check':label,'detail':detail})

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    for width, height in [(320,812),(390,844),(768,1024),(1366,768)]:
        context = browser.new_context(viewport={'width':width,'height':height}, reduced_motion='reduce')
        page = context.new_page()
        page.set_default_timeout(10000)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        for filename in PAGES:
            errors.clear()
            response = page.goto(BASE + '/' + filename, wait_until='domcontentloaded')
            page.wait_for_timeout(650)
            check(response.status == 200, f'{filename}@{width}: HTTP 200')
            metrics = page.evaluate('''() => ({width:innerWidth, documentWidth:document.documentElement.scrollWidth,
                title:document.querySelector('h1')?.textContent.trim(),
                overflowing:[...document.querySelectorAll('main *')].filter(e=>{
                    const r=e.getBoundingClientRect();return r.width>0&&(r.right>innerWidth+2||r.left < -2);
                }).slice(0,12).map(e=>({tag:e.tagName,class:e.className,left:Math.round(e.getBoundingClientRect().left),right:Math.round(e.getBoundingClientRect().right)}))})''')
            report['viewports'].append({'page':filename,'width':width,'metrics':metrics,'javascriptErrors':errors.copy()})
            check(metrics['documentWidth'] <= width + 2, f'{filename}@{width}: no horizontal overflow', metrics)
            check(bool(metrics['title']), f'{filename}@{width}: visible page identity')
            check(not errors, f'{filename}@{width}: no JavaScript exceptions', errors.copy())
            if width in [390,1366]:
                page.screenshot(path=str(RESULTS / f'{filename[:-5]}-{width}.png'))
            if width < 1180:
                menu = page.locator('.gw-menu')
                check(menu.is_visible(), f'{filename}@{width}: mobile menu button')
                menu.click()
                check(menu.get_attribute('aria-expanded') == 'true', f'{filename}@{width}: menu opens')
                check(page.locator('.gw-nav a[href="contact.html"]').is_visible(), f'{filename}@{width}: contact reachable')
                page.keyboard.press('Escape')
                check(menu.get_attribute('aria-expanded') == 'false', f'{filename}@{width}: Escape closes menu')
            if filename == 'peirong-lin.html' and width in [320,390]:
                y = page.locator('h1').bounding_box()['y']
                check(y < 450, f'{filename}@{width}: name on first screen', y)
        context.close()

    context = browser.new_context(viewport={'width':390,'height':844})
    page = context.new_page()
    page.set_default_timeout(10000)
    page.goto(BASE+'/publications.html', wait_until='domcontentloaded')
    page.wait_for_timeout(200)
    count = page.locator('.publications-content .pub-item').count()
    page.locator('#publication-search').fill('GSHA')
    check(page.locator('.publications-content .pub-item:not([hidden])').count() > 0, 'Publication search finds GSHA')
    page.locator('#publication-search').fill('no-such-paper-unique-test')
    check(page.locator('.publications-content .pub-item:not([hidden])').count() == 0, 'Publication search supports no results')
    page.locator('#publication-reset').click()
    check(page.locator('.publications-content .pub-item:not([hidden])').count() == count, 'Publication reset restores every record')
    page.locator('#publication-collapse').click()
    check(page.locator('.publications-content details[open]').count() == 0, 'Collapse all publication years')
    first_id = page.locator('.publications-content .pub-item').first.get_attribute('id')
    page.goto(BASE+'/publications.html#'+first_id, wait_until='domcontentloaded')
    page.wait_for_timeout(250)
    check(page.locator('#'+first_id).is_visible(), 'Direct publication link opens its year')
    page.locator('#publication-expand').click()
    copy_button = page.locator('.publications-content [data-copy]').first
    copy_button.click()
    check(page.locator('.gw-citation-text').first.is_visible(), 'Citation text is selectable')

    page.goto(BASE+'/paper-radar.html', wait_until='domcontentloaded')
    page.wait_for_function("!document.getElementById('radar-status').textContent.startsWith('Loading')")
    check(page.locator('.radar-day').count() == 7, 'Radar defaults to seven archive days')
    page.locator('#radar-window').select_option('30')
    check(page.locator('.radar-day').count() >= 7, 'Radar full archive expands date range')
    page.locator('#radar-search').fill('no-such-paper-unique-test')
    check(page.locator('article.radar-item').count() == 0, 'Radar search filters results')
    page.locator('#radar-reset').click()
    check(page.locator('.radar-day').count() == 7, 'Radar reset restores compact window')
    data = json.loads((SITE/'assets/data/paper-radar.json').read_text())
    page.locator('#radar-date').fill(data['targetDate'])
    page.locator('#radar-date').dispatch_event('change')
    check(page.locator('.radar-day').count() == 1, 'Radar date selection isolates one day')
    context.close()

    nojs = browser.new_context(viewport={'width':390,'height':844}, java_script_enabled=False)
    page = nojs.new_page()
    for filename in ['index.html','publications.html','peirong-lin.html','Resources.html']:
        page.goto(BASE+'/'+filename, wait_until='domcontentloaded')
        check(page.locator('.gw-nav a[href="Resources.html"]').is_visible(), f'{filename}: navigation works without JavaScript')
        if filename == 'publications.html':
            check(page.locator('.publications-content .pub-item').first.is_visible(), 'Publication content works without JavaScript')
    nojs.close()
    browser.close()
server.shutdown()
(RESULTS/'browser-checks.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'viewportCases':len(report['viewports']), 'checks':len(report['interactions']), 'failures':report['failures']},indent=2))
sys.exit(1 if report['failures'] else 0)
