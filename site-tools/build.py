#!/usr/bin/env python3
"""Build the public site without changing scientific source documents.

The root HTML files remain the editorial source of truth. Shared navigation,
accessibility, publication discovery and verified data links are assembled here,
not by mutating scientific text in a navigation script after page load.
"""
from __future__ import annotations
import copy
import hashlib
import json
import os
import posixpath
import re
import shutil
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote, urlsplit
from bs4 import BeautifulSoup, NavigableString

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_site'
BASE = 'https://geowaterpku.github.io/'
BUILD = os.environ.get('GITHUB_SHA', 'local')[:12]
NAV = [('Home', '/', 'home'), ('People', 'people.html', 'people'),
       ('Peirong Lin', 'peirong-lin.html', 'cv'),
       ('Research', 'current-research.html', 'research'),
       ('Publications', 'publications.html', 'publications'),
       ('Teaching', 'teaching.html', 'teaching'),
       ('Open Data', 'Resources.html', 'resources'),
       ('Paper Radar', 'paper-radar.html', 'paper-radar'),
       ('Contact', 'contact.html', 'contact')]
DATA = {
 'GRADES': {'id':'grades', 'url':'https://www.reachhydro.org/home/records/grades',
   'paper':'https://doi.org/10.1029/2019WR025287', 'match':'Global reconstruction of naturalized river flows',
   'status':'Legacy release', 'facts':['1980–2013', 'Daily discharge', '2.94 million reaches'],
   'note':'The original GRADES release is retained for reproducibility. Its maintainers direct new applications to GRADES-hydroDL; check the associated hydrography version before combining products.'},
 'MERIT-Basins': {'id':'merit-basins', 'url':'https://www.reachhydro.org/home/params/merit-basins',
   'paper':'https://doi.org/10.1029/2019WR025287', 'match':'Global reconstruction of naturalized river flows',
   'status':'Data portal available', 'facts':['Vector flowlines and catchments', '25 km² threshold', 'Shapefile'],
   'note':'The official portal distinguishes hydrography versions and coastal bug fixes. Use the version required by the discharge product or model you are working with.'},
 'MERIT-Hydro-Vectors': {'id':'merit-hydro-vectors', 'url':'https://www.reachhydro.org/home/params/global-drainage-density',
   'match':'variable drainage density', 'status':'Data portal available',
   'facts':['Variable drainage density', 'Vector hydrography', 'Global coverage'],
   'note':'The official Global Drainage Density page provides the variable-drainage-density hydrography, download information and its Scientific Data reference.'},
 'GSHA': {'id':'gsha', 'url':'https://doi.org/10.5281/zenodo.8090704',
   'extra':[('Additional data record','https://doi.org/10.5281/zenodo.10433905')],
   'paper':'https://essd.copernicus.org/articles/16/1559/2024/', 'match':'A synthesis of global streamflow',
   'status':'Data records available', 'facts':['Streamflow characteristics', 'Hydrometeorology', 'Dynamic catchment attributes'],
   'note':'Both data records are identified in the publication. Review the files, version history and reuse terms on each record before downloading.'},
 'SHIFT': {'id':'shift', 'url':'https://doi.org/10.5281/zenodo.11835133',
   'extra':[('Core code','https://doi.org/10.5281/zenodo.13311752')],
   'paper':'https://essd.copernicus.org/articles/16/3873/2024/', 'match':'SHIFT:',
   'status':'Data and code available', 'facts':['90 m and 1 km', 'Geomorphic floodplains', 'Spatially varying parameters'],
   'note':'Use the dataset record for files and version information, the paper for methodology, and the separate code record for terrain analysis and parameter estimation.'}
}
TOPICS = {
 'Remote sensing': r'remote sensing|satellite|swot|\bswap\b|river width|spaceborne',
 'Floods and society': r'flood|levee|urban|human|reservoir',
 'Hydrological modeling': r'model|simulation|routing|parameter|noah|wrf|lstm',
 'Data products': r'dataset|database|\bgsha\b|\bshift\b|reconstruction|river network',
 'Hydroclimate': r'climate|snow|cryosphere|temperature|precipitation|evapotranspiration'
}

def fragment(markup):
    return BeautifulSoup(markup, 'html.parser')

def tag(markup):
    return next(c for c in fragment(markup).contents if getattr(c, 'name', None))

def text(el):
    return el.get_text(' ', strip=True) if el else ''

def add_class(el, name):
    el['class'] = list(dict.fromkeys(el.get('class', []) + [name]))

def external(href, label, cls='gw-link'):
    return f'<a class="{cls}" href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(label)} <span aria-hidden="true">↗</span></a>'

def publication_records(soup):
    records = []
    for item in soup.select('.pub-item'):
        title = text(item.select_one('.pub-title'))
        year = item.find_parent(class_='year-block')
        group = year.get('id', '') if year else ''
        a = item.select_one('.pub-journal a[href], .pub-title a[href], a.pub-figure[href]')
        href = a.get('href', '') if a else ''
        journal = text(item.select_one('.pub-journal'))
        status = 'Submitted / in revision' if group == 'submitted' else (
            'Preprint' if re.search(r'egusphere|arxiv|preprint', href + ' ' + journal, re.I) else
            'Dissertation' if group == 'dissertation' else 'Publication')
        records.append({'title':title, 'authors':text(item.select_one('.pub-authors')),
            'journal':journal, 'href':href, 'group':group, 'status':status,
            'id':'paper-' + hashlib.sha1(title.encode()).hexdigest()[:10],
            'image':copy.deepcopy(item.select_one('.pub-figure img')),
            'topics':[k for k, v in TOPICS.items() if re.search(v, title, re.I)]})
    return records

def find_record(records, needle):
    return next((r for r in records if needle.casefold() in r['title'].casefold()), None)

def highlights(records):
    cards = []
    choices = [('SHIFT:', 'Mapping global floodplains',
                'Spatially varying parameters support a global geomorphic floodplain map.', 'shift'),
               ('A synthesis of global streamflow', 'Connecting rivers and their catchments',
                'GSHA brings streamflow characteristics, hydrometeorology and dynamic catchment attributes together.', 'gsha'),
               ('Global reconstruction of naturalized river flows', 'Reconstructing reach-scale river flows',
                'Naturalized river-flow reconstruction at 2.94 million reaches provides a foundation for river-centric analyses.', 'grades')]
    for needle, heading, description, dataset in choices:
        r = find_record(records, needle)
        if not r:
            continue
        img = str(r['image']) if r['image'] else ''
        cards.append(f'<article class="gw-feature"><div class="gw-feature__image">{img}</div>'
            f'<div class="gw-feature__copy"><p class="gw-kicker">Research highlight</p><h3>{heading}</h3>'
            f'<p>{description}</p><p class="gw-feature__source">{escape(r["journal"])}</p>'
            f'<div class="gw-actions"><a href="publications.html#{r["id"]}">View publication →</a>'
            f'<a href="Resources.html#{dataset}">Access data →</a></div></div></article>')
    return '<div class="gw-feature-grid">' + ''.join(cards) + '</div>'

def make_nav(page):
    parts = []
    for label, href, key in NAV:
        if key == 'research':
            active = page in ['research','current-research','previous-research']
            sub = ''.join(f'<li><a href="{u}"' + (' aria-current="page"' if page == p else '') + f'>{l}</a></li>'
                for l,u,p in [('Current Research','current-research.html','current-research'),
                              ('Past Research','research.html','research')])
            parts.append(f'<li><details class="gw-research"><summary' + (' class="is-current"' if active else '') +
                         f'>Research <span aria-hidden="true">⌄</span></summary><ul>{sub}</ul></details></li>')
        else:
            current = ' aria-current="page"' if page == key else ''
            parts.append(f'<li><a href="{href}"{current}>{label}</a></li>')
    return tag('<header class="gw-header"><div class="gw-header__inner">'
        '<a class="gw-brand" href="/" aria-label="GeoWater Lab home"><span>GeoWater Lab</span><small>Peking University</small></a>'
        '<button class="gw-menu" type="button" aria-expanded="false" aria-controls="gw-primary-menu">'
        '<span class="gw-menu__icon" aria-hidden="true">☰</span> <span>Menu</span></button>'
        '<nav id="gw-primary-menu" class="gw-nav" aria-label="Primary navigation"><ul>' + ''.join(parts) + '</ul></nav>'
        '</div></header>')

def prepare_home(soup, records):
    main = soup.select_one('main')
    hero_link = soup.select_one('.home-v2-scroll-link')
    if hero_link:
        hero_link.replace_with(tag('<div class="gw-actions gw-actions--hero"><a class="gw-button" href="current-research.html">Explore research →</a>'
            '<a class="gw-button gw-button--outline" href="#selected-research">Selected research ↓</a></div>'))
    titles = ['A changing water cycle', 'River structure and flood risk', 'Human activities and flood impacts']
    for i, block in enumerate(soup.select('.home-question')):
        h2 = block.select_one('h2')
        if h2 and i < len(titles):
            full = text(h2)
            h2.string = titles[i]
            h2.insert_after(tag(f'<p class="gw-full-question">{escape(full)}</p>'))
            block.select_one('.home-question__copy a')['href'] = f'current-research.html#question-{i+1}'
    methods_title = soup.select_one('#how-we-work-title')
    if methods_title:
        methods_title.string = 'We are developing a “big data hydrology” program at PKU.'
        summary = methods_title.find_next_sibling('p')
        if summary:
            summary.string = 'Our spatially explicit, river-centric approach brings together four complementary methodological pillars to observe, represent, model, and parameterize heterogeneous river systems.'
    for img in soup.select('.home-methods__media img'):
        img['src'] = 'assets/home/how-we-work-framework.svg'
        img['alt'] = 'Four methodological pillars supporting Big Data Hydrology at Peking University'
    caption = soup.select_one('.home-methods__media figcaption')
    if caption:
        caption.string = 'Four methodological pillars of our Big Data Hydrology program at PKU'
    enabling = soup.select_one('.home-methods__enabling')
    if enabling:
        enabling.decompose()
    featured = tag('<section class="gw-section" id="selected-research" aria-labelledby="selected-title"><div class="gw-shell">'
        '<div class="gw-section-heading"><p class="gw-kicker">From questions to contributions</p><h2 id="selected-title">Selected research</h2>'
        '<p>Explore the publications and reusable data behind our research.</p></div>' + highlights(records) + '</div></section>')
    anchor = soup.select_one('#how-we-work') or soup.select_one('.home-v2-news')
    if anchor:
        anchor.insert_before(featured)
        anchor.insert_before(tag('<section class="gw-data-strip"><div class="gw-shell"><div><p class="gw-kicker">Open research infrastructure</p>'
            '<h2>Find the data. Reuse the science.</h2><p>River discharge, river networks, catchment attributes and global floodplains.</p></div>'
            '<a class="gw-button" href="Resources.html">Explore five data products →</a></div></section>'))
    news = soup.select_one('.home-v2-news')
    if news:
        old_list = news.select_one('.home-v2-news-list')
        hiring = []
        if old_list:
            for article in list(old_list.select('article'))[:2]:
                if text(article.select_one('.home-v2-news-index')) == 'Open':
                    hiring.append(str(article.extract()))
            old_list.extract()
        old_archive = news.select_one('.home-v2-news-archive')
        if old_archive:
            old_archive.extract()
            summary = old_archive.select_one('summary')
            if summary:
                summary.string = 'Earlier lab news · 2020–2024'
        recent = [r for r in records if re.fullmatch(r'y\d{4}', r['group']) and r['status'] == 'Publication'][:3]
        items = ''.join(f'<article><time>{escape(r["group"][1:])}</time><div><h3><a href="publications.html#{r["id"]}">{escape(r["title"])}</a></h3><p>{escape(r["journal"])}</p></div></article>' for r in recent)
        archive = (str(old_list) if old_list else '') + (str(old_archive) if old_archive else '')
        news.clear()
        news.append(tag('<div class="gw-shell"><div class="gw-section-heading"><p class="gw-kicker">Latest on our publication list</p>'
            '<h2 id="news-title">Recent publications</h2><p>Publication years follow the lab’s maintained bibliography.</p></div>'
            '<div class="gw-updates">' + items + '</div><a class="gw-inline-link" href="publications.html">View the complete publication list →</a>'
            '<details class="gw-archive"><summary>Lab news archive · 2020–2025</summary>' + archive + '</details></div>'))
        join = tag('<section class="gw-section gw-join" id="join-the-lab"><div class="gw-shell"><p class="gw-kicker">Join the lab</p>'
            '<h2>Work with GeoWater.</h2><p>We welcome motivated postdoctoral researchers, graduate students and undergraduate researchers.</p>'
            '<div class="gw-actions"><a class="gw-button" href="contact.html#join-lab">Explore opportunities →</a><a href="people.html">Meet the team →</a></div>'
            '<details class="gw-archive"><summary>Full recruitment information</summary>' + ''.join(hiring) + '</details></div></section>')
        news.insert_after(join)

def prepare_publications(soup, records):
    for script in list(soup.find_all('script')):
        if script.get('type') != 'application/ld+json':
            script.decompose()
    for cloud in soup.select('.word-cloud-container'):
        cloud.decompose()
    h2 = soup.select_one('#published > h2')
    if h2:
        h2.string = 'Publications & manuscripts'
    intro = soup.select_one('.publications-heading__copy > p:last-child')
    if intro:
        intro.string = 'Find articles, data publications and manuscripts by title, author, topic or year. Submission and preprint statuses are shown separately.'
    heading = soup.select_one('.publications-heading')
    if heading:
        heading.insert_after(tag('<details class="gw-selected-publications"><summary>Selected research highlights</summary>' + highlights(records) + '</details>'))
    for item, r in zip(soup.select('.pub-item'), records):
        item['id'] = r['id']
        item['data-search'] = ' '.join([r['title'],r['authors'],r['journal']]).casefold()
        item['data-topics'] = '|'.join(r['topics'])
        item['data-group'] = r['group']
        title = item.select_one('.pub-title')
        if title and r['href'] and not title.find('a'):
            a = soup.new_tag('a', href=r['href'], target='_blank', rel='noopener noreferrer')
            a['class'] = ['pub-title-link']
            for child in list(title.contents):
                a.append(child.extract())
            title.append(a)
        if r['status'] != 'Publication':
            title.insert_before(tag(f'<p class="gw-status-label">{escape(r["status"])}</p>'))
        if r['href']:
            citation = ' '.join([r['authors'],r['title'],r['journal'],r['href']])
            holder = item.select_one('.pub-entry-copy') or item
            holder.append(tag('<button class="gw-copy js-only" type="button" data-copy="' + escape(citation, quote=True) + '">Copy citation</button>'))
    content = soup.select_one('.publications-content')
    submitted = soup.select_one('#submitted')
    if submitted and content:
        content.append(submitted.extract())
    for block in soup.select('.year-block'):
        block.name = 'details'
        block['open'] = ''
        title = block.select_one('.year-title')
        if title:
            title.name = 'summary'
            count = len(block.select('.pub-item'))
            meta = title.select_one('.year-meta')
            if meta:
                meta.string = f'{count} ' + ('entry' if count == 1 else 'entries')
    section = soup.select_one('#published')
    options = ''.join(f'<option value="{escape(k, quote=True)}">{escape(k)}</option>' for k in TOPICS)
    groups = ''.join(f'<option value="{b.get("id")}">{escape(text(b.select_one(".year-title > span")))}</option>' for b in soup.select('.year-block'))
    controls = tag('<div class="gw-search-controls js-only" role="search" aria-label="Search publications">'
        '<label>Title, author or journal<input id="publication-search" type="search" placeholder="Search publications…" autocomplete="off"></label>'
        '<label>Topic<select id="publication-topic"><option value="">All topics</option>' + options + '</select></label>'
        '<label>Year / section<select id="publication-year"><option value="">All years</option>' + groups + '</select></label>'
        '<div class="gw-search-actions"><button id="publication-reset" type="button">Reset filters</button><button id="publication-expand" type="button">Expand all years</button>'
        '<button id="publication-collapse" type="button">Collapse all years</button></div><p id="publication-results" role="status" aria-live="polite"></p></div>')
    if section:
        legend = section.select_one('.legend')
        (legend or section.select_one('h2')).insert_after(controls)
    timeline = soup.select_one('.publications-sidebar .timeline-nav')
    if timeline:
        links = {a.get('href'):a.extract() for a in list(timeline.select('a[href]'))}
        timeline.clear()
        for block in soup.select('.year-block'):
            a = links.get('#' + block['id'])
            if a:
                timeline.append(a)
        timeline['aria-label'] = 'Publication years and sections'

def prepare_profile(soup, legacy):
    hero = soup.select_one('#experiences')
    title = soup.select_one('.title-with-gs')
    photo = soup.select_one('.headshot')
    if not hero or not title or not photo:
        return
    photo_parent = photo.parent
    main_content = hero.select_one('.hero-main-content')
    announcements = hero.select_one('.hero-announcements')
    announcement_html = str(announcements.extract()) if announcements else ''
    profile = tag('<div class="gw-profile"><div class="gw-profile__intro"></div><div class="gw-profile__portrait"></div></div>')
    profile.select_one('.gw-profile__intro').append(title.extract())
    profile.select_one('.gw-profile__intro').append(tag('<p class="gw-profile__description">Hydrologist and GIS researcher studying global rivers, terrestrial water cycling, remote sensing, river modeling and flood–human interactions.</p>'))
    profile.select_one('.gw-profile__portrait').append(photo.extract())
    if main_content:
        main_content.decompose()
    if photo_parent and photo_parent is not hero:
        photo_parent.decompose()
    hero.insert(0, profile)
    impact_match = re.search(r'impactCard\.innerHTML\s*=\s*`([\s\S]*?)`', legacy)
    if impact_match:
        impact = tag('<details class="gw-profile-impact"><summary>Academic impact & citation history</summary>'
            '<aside class="scholar-impact-card is-pending" data-scholar-impact aria-label="Google Scholar impact metrics for Peirong Lin">' + impact_match.group(1) + '</aside></details>')
        profile.insert_after(impact)
        soup.head.append(tag('<link rel="stylesheet" href="assets/scholar-impact.css">'))
        soup.body.append(tag('<script src="assets/scholar-impact.js" defer></script>'))
    if announcement_html:
        profile.insert_after(tag('<details class="gw-profile-openings"><summary>Lab openings and recruitment information</summary>' + announcement_html + '</details>'))
    sidebar = soup.select_one('.home-sidebar')
    if sidebar:
        main_column = soup.select_one('.main-column')
        if main_column:
            sidebar.extract()
            hero.insert_after(sidebar)


def prepare_resources(soup, records):
    for card in soup.select('.resource-card'):
        key = text(card.select_one('h3'))
        spec = DATA.get(key)
        if not spec:
            continue
        card['id'] = spec['id']
        state = card.select_one('.resource-card__status')
        if state:
            state.string = spec['status']
        facts = card.select_one('.resource-card__facts')
        if facts:
            facts.clear()
            for fact in spec['facts']:
                facts.append(tag('<span>' + escape(fact) + '</span>'))
        record = find_record(records, spec['match'])
        paper = spec.get('paper') or (record['href'] if record else '')
        links = external(spec['url'], 'Data & documentation', 'gw-button')
        if paper:
            links += external(paper, 'Read paper')
        for label, href in spec.get('extra', []):
            links += external(href, label)
        holder = card.select_one('.resource-card__content')
        holder.append(tag('<div class="gw-actions gw-data-actions">' + links + '</div>'))
        holder.append(tag('<p class="gw-data-note">' + escape(spec['note']) + '</p>'))
        if record:
            cite = ' '.join([record['authors'],record['title'],record['journal'],paper])
            holder.append(tag('<details class="gw-citation"><summary>Paper citation & reuse</summary><p>' + escape(cite) + '</p>'
                '<button type="button" class="gw-copy js-only" data-copy="' + escape(cite, quote=True) + '">Copy paper citation</button>'
                '<p>Also cite the dataset version you use. The linked repository is authoritative for version history, file formats and license terms.</p></details>'))
    extension_links = {'GRFR':'https://www.reachhydro.org/home/records/grfr',
        'GRADES-hydroDL':'https://www.reachhydro.org/home/records/grades-hydrodl'}
    for entry in soup.select('.resource-related__item'):
        name = text(entry.select_one('strong'))
        placeholder = entry.select_one('em')
        if placeholder:
            if name in extension_links:
                placeholder.replace_with(tag(external(extension_links[name], 'Open project')))
            else:
                placeholder.replace_with(tag('<a href="mailto:peironglinlin@pku.edu.cn?subject=' + quote('Question about ' + name) + '">Enquire about access →</a>'))
    p = soup.select_one('.resources-status__grid > div > p')
    if p:
        p.clear()
        p.append('Follow the official data portals and repositories linked above for downloads, version history and reuse terms. Cite both the paper and the exact data version used. ')
        p.append(tag('<a href="contact.html">Contact the lab with data questions →</a>'))
    hero = soup.select_one('.resources-hero')
    if hero:
        links = ''.join(f'<a href="#{v["id"]}">{escape(k)}</a>' for k,v in DATA.items())
        hero.insert_after(tag('<nav class="gw-section-nav" aria-label="Data products">' + links + '</nav>'))


def prepare_research(soup):
    for i, card in enumerate(soup.select('.research-overarching__card'), 1):
        card['id'] = f'question-{i}'
    projects = soup.select('.research-project')
    links = '<a href="#scientific-questions">Scientific questions</a>'
    for i, project in enumerate(projects, 1):
        project['id'] = f'project-{i}'
        kicker = text(project.select_one('.research-kicker')) or f'Project {i}'
        links += f'<a href="#project-{i}">{i:02d} · {escape(kicker)}</a>'
    links += '<a href="Resources.html">Open data →</a>'
    hero = soup.select_one('.research-hero')
    if hero:
        hero.insert_after(tag('<nav class="gw-section-nav" aria-label="Research sections">' + links + '</nav>'))


def prepare_contact(soup):
    main = soup.select_one('main, .page')
    if not main:
        return
    block = tag('<section class="gw-section gw-contact-paths" id="join-lab"><div class="gw-shell"><div class="gw-section-heading">'
        '<p class="gw-kicker">Start a conversation</p><h2>Study or collaborate with us.</h2></div><div class="gw-contact-grid">'
        '<article><h3>Prospective students & postdocs</h3><p>For an initial enquiry, it is helpful to introduce your academic background, research interests and intended study period. You may include a CV or links to relevant work.</p>'
        '<a class="gw-button" href="mailto:peironglinlin@pku.edu.cn?subject=GeoWater%20Lab%20research%20opportunity">Enquire about opportunities →</a>'
        '<p class="gw-data-note">An email enquiry is not a formal application or an offer of admission.</p></article>'
        '<article><h3>Research & data collaboration</h3><p>Outline your research question, the relevant project or dataset, and the type of collaboration or data assistance you are seeking.</p>'
        '<div class="gw-actions"><a href="mailto:peironglinlin@pku.edu.cn?subject=GeoWater%20research%20collaboration">Contact the lab →</a><a href="Resources.html">Browse open data →</a></div></article>'
        '</div></div></section>')
    first_section = main.find('section', recursive=False)
    if first_section:
        first_section.insert_after(block)
    else:
        main.insert(0, block)
    for video in soup.find_all('video'):
        video['preload'] = 'none'
        video['controls'] = ''
        video.attrs.pop('autoplay', None)
        video.attrs.pop('loop', None)


def prepare_radar(soup):
    intro = soup.select_one('.radar-intro')
    if intro:
        original = text(intro)
        intro.string = 'Scan recent geoscience papers by topic, date or title. Expand the AI Chinese guide when a paper is relevant to your work.'
        intro.insert_after(tag('<details class="gw-radar-about"><summary>About this radar & its limitations</summary><p>' + escape(original) + '</p>'
            '<p>AI guides are reading aids, not a substitute for the paper. Title-only guides are explicitly marked. A successful crawl with no matches is different from a date that has not been checked.</p></details>'))
    panel = soup.select_one('.radar-panel')
    if panel:
        filters = soup.select_one('#radar-filters')
        filters.insert_before(tag('<div class="gw-search-controls" role="search" aria-label="Search paper radar">'
            '<label>Title, author or journal<input type="search" id="radar-search" placeholder="Search papers…" autocomplete="off"></label>'
            '<label>Archive window<select id="radar-window"><option value="7">Latest 7 days</option><option value="30">Full archive</option></select></label>'
            '<label>Publication date<input id="radar-date" type="date"></label><div class="gw-search-actions"><button type="button" id="radar-reset">Reset filters</button>'
            '<button type="button" id="radar-expand">Expand dates</button><button type="button" id="radar-collapse">Collapse dates</button></div></div>'))
        panel.append(tag('<noscript><p>Interactive filters require JavaScript. <a href="assets/data/paper-radar.json">Read the paper data archive (JSON)</a>.</p></noscript>'))


def compile_css(soup, filename):
    imports, sheets = [], []
    for el in list(soup.head.find_all(['link','style'])):
        if el.name == 'link' and ('stylesheet' not in el.get('rel', []) or not el.get('href','').startswith('assets/')):
            continue
        if el.name == 'style':
            content, basepath = el.string or el.get_text(), ''
        else:
            path = urlsplit(el['href']).path
            source = OUT / path
            if not source.exists():
                raise RuntimeError(f'Missing stylesheet: {path}')
            content, basepath = source.read_text(), posixpath.dirname(path)
        def rewrite_url(m):
            value = m.group(1).strip().strip('\"\'')
            if value.startswith(('http:','https:','data:','//','#','/')):
                return m.group(0)
            return 'url("/' + posixpath.normpath(posixpath.join(basepath,value)) + '")'
        content = re.sub(r'url\(([^)]+)\)', rewrite_url, content)
        imports.extend(re.findall(r'@import\s+[^;]+;', content))
        content = re.sub(r'@import\s+[^;]+;', '', content)
        sheets.append(content)
        el.decompose()
    css = '\n'.join(dict.fromkeys(imports)) + '\n' + '\n'.join(sheets)
    digest = hashlib.sha256(css.encode()).hexdigest()[:10]
    csspath = f'assets/built-{Path(filename).stem}-{digest}.css'
    (OUT / csspath).write_text(css)
    soup.head.append(tag(f'<link rel="stylesheet" href="{csspath}">'))


def common(soup, filename, legacy_css):
    if not soup.body or not soup.head or soup.select_one('meta[http-equiv="refresh"]'):
        return
    page = soup.body.get('data-page','')
    if page == 'team':
        page = 'people'
    add_class(soup.body, 'gw-site')
    for script in list(soup.find_all('script', src=True)):
        if re.search(r'/(nav|home-v2)\.js', script['src']):
            script.decompose()
    for header in soup.select('header.primary-nav'):
        header.decompose()
    main = soup.find('main') or soup.select_one('.page')
    if main:
        main.name = 'main'
        main['id'] = main.get('id', 'main-content')
        main['tabindex'] = '-1'
        soup.body.insert(0, tag(f'<a class="gw-skip" href="#{main["id"]}">Skip to main content</a>'))
    soup.body.insert(1, make_nav(page))
    for footer in soup.select('.site-copyright'):
        footer.decompose()
    year = datetime.now(timezone.utc).year
    soup.body.append(tag(f'<footer class="gw-footer"><div class="gw-shell"><div><strong>GeoWater Research Lab</strong><p>Peking University · School of Earth and Space Sciences</p></div>'
        '<nav aria-label="Footer navigation"><a href="publications.html">Publications</a><a href="Resources.html">Open data</a><a href="contact.html">Contact & opportunities</a></nav>'
        f'<p class="gw-copyright">© {year} GeoWater Research Lab. Dataset reuse is governed by each repository’s license.</p></div></footer>'))
    for node in list(soup.find_all(string=True)):
        if node.parent.name not in ['script','style']:
            new = re.sub(r'\bEarth observation\b', 'Earth observations', str(node))
            if new != str(node):
                node.replace_with(NavigableString(new))
    for row in soup.select('.person-row'):
        if text(row.select_one('h3')) in ['Zimin Yuan','Haomei Lin']:
            role = row.select_one('.role')
            if role:
                role.string = text(role).replace('PhD student','PhD candidate')
    if page == 'people':
        for impact in soup.select('[data-scholar-impact]'):
            impact.decompose()
    h1 = soup.find('h1')
    if h1 and page not in ['home','cv']:
        hero = h1.find_parent('section') or h1.find_parent('header')
        if hero:
            add_class(hero, 'gw-inner-hero')
    for a in soup.select('a[target="_blank"]'):
        a['rel'] = list(dict.fromkeys(a.get('rel', []) + ['noopener','noreferrer']))
    for image in soup.find_all('img'):
        image['decoding'] = 'async'
        image['alt'] = image.get('alt', '')
    for style in soup.select('#cv-nav-hard-fix'):
        style.decompose()
    soup.head.append(tag('<link rel="stylesheet" href="assets/legacy-static.css">'))
    soup.head.append(tag('<link rel="stylesheet" href="assets/site-ui.css">'))
    soup.head.append(tag('<script>document.documentElement.classList.add("js");</script>'))
    soup.head.append(tag(f'<meta name="geowater-build" content="{BUILD}">'))
    if not soup.select_one('link[rel="icon"]'):
        soup.head.append(tag('<link rel="icon" href="/assets/geowater-icon.svg" type="image/svg+xml">'))
    title = text(soup.title)
    description = soup.select_one('meta[name="description"]')
    canonical = soup.select_one('link[rel="canonical"]')
    for prop, value in [('og:title',title), ('og:description',description.get('content','') if description else title),
                        ('og:type','website'), ('og:url',canonical.get('href') if canonical else BASE + filename),
                        ('og:image',BASE + 'assets/home/geowater-river-city-v1.webp')]:
        if not soup.select_one(f'meta[property="{prop}"]'):
            soup.head.append(tag(f'<meta property="{prop}" content="{escape(value, quote=True)}">'))
    soup.body.append(tag('<script src="assets/site-ui.js" defer></script>'))
    compile_css(soup, filename)
    for script in soup.select('script[src]'):
        src = urlsplit(script['src']).path
        file = OUT / src
        if src.startswith('assets/') and file.is_file():
            script['src'] = src + '?v=' + hashlib.sha256(file.read_bytes()).hexdigest()[:10]


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    excluded = {'.git','.github','_site','node_modules','site-tools','test-results','docs','__pycache__','.bg3-upload-hires'}
    shutil.copytree(ROOT, OUT, ignore=lambda path,names: [n for n in names if n in excluded or n.startswith('.git')])
    legacy = (ROOT / 'assets/nav.js').read_text()
    legacy_css = '\n'.join(s for s in re.findall(r'[\w.]+\.textContent\s*=\s*`([\s\S]*?)`', legacy) if '{' in s and '${' not in s)
    (OUT / 'assets/legacy-static.css').write_text(legacy_css)
    pub_source = BeautifulSoup((ROOT / 'publications.html').read_text(), 'html.parser')
    records = publication_records(pub_source)
    (OUT / 'assets/data/publication-index.json').write_text(json.dumps([{k:v for k,v in r.items() if k != 'image'} for r in records], ensure_ascii=False, indent=2))
    for path in sorted(ROOT.glob('*.html')):
        soup = BeautifulSoup(path.read_text(), 'html.parser')
        if path.name == 'index.html':
            prepare_home(soup, records)
        elif path.name == 'publications.html':
            prepare_publications(soup, records)
        elif path.name in ['peirong-lin.html','cv.html'] and not soup.select_one('meta[http-equiv="refresh"]'):
            prepare_profile(soup, legacy)
        elif path.name == 'Resources.html':
            prepare_resources(soup, records)
        elif path.name == 'current-research.html':
            prepare_research(soup)
        elif path.name == 'contact.html':
            prepare_contact(soup)
        elif path.name == 'paper-radar.html':
            prepare_radar(soup)
        elif path.name == 'teaching.html':
            host = soup.select_one('main, .page')
            if host:
                host.append(tag('<section class="gw-course-enquiry"><h2>Course information</h2><p>For course availability, syllabi or teaching-material enquiries, please contact the instructor. Materials are linked only when a public release is available.</p><a href="mailto:peironglinlin@pku.edu.cn?subject=Course%20information%20enquiry">Enquire about teaching →</a></section>'))
        common(soup, path.name, legacy_css)
        (OUT / path.name).write_text(str(soup), encoding='utf-8')
    notfound = BeautifulSoup('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><base href="/"><title>Page not found | GeoWater Lab</title><meta name="robots" content="noindex"></head><body><main class="gw-shell gw-not-found"><p class="gw-kicker">404</p><h1>This page could not be found.</h1><p>The address may have changed. Continue to our research, publications or open data.</p><div class="gw-actions"><a class="gw-button" href="/">Go to the homepage →</a><a href="Resources.html">Open data →</a></div></main></body></html>', 'html.parser')
    common(notfound, '404.html', legacy_css)
    (OUT / '404.html').write_text(str(notfound))
    (OUT / '.nojekyll').touch()
    pages = [p.name for p in ROOT.glob('*.html') if p.name not in ['cv.html','team.html','404.html']]
    urls = ''.join('<url><loc>' + BASE + ('' if p == 'index.html' else p) + '</loc></url>' for p in sorted(pages))
    (OUT / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + urls + '</urlset>')
    if not (OUT / 'robots.txt').exists():
        (OUT / 'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: ' + BASE + 'sitemap.xml\n')
    (OUT / 'build-info.json').write_text(json.dumps({'commit':BUILD,'builtAt':datetime.now(timezone.utc).isoformat(),'pages':len(pages),'publications':len(records)}))
    print(json.dumps({'build':BUILD,'htmlPages':len(list(OUT.glob('*.html'))),'publicationEntries':len(records)}, indent=2))

if __name__ == '__main__':
    main()
