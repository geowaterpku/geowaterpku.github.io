#!/usr/bin/env python3
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

KEYWORD_QUERIES = {
    "river modeling": '"river modeling" OR "river modelling"',
    "global hydrology": '"global hydrology"',
    "flood-human interaction": '"flood-human interaction" OR "human-flood interaction" OR "human flood interaction"',
    "river remote sensing": '"river remote sensing" OR "remote sensing of rivers"',
    "hydroclimate": 'hydroclimate OR hydroclimatic',
    "floods": 'flood OR floods OR flooding',
}
KEYWORDS = list(KEYWORD_QUERIES)

ALLOWED_JOURNAL_PATTERNS = [
    r"^Nature$",
    r"^Science$",
    r"^Proceedings of the National Academy of Sciences(?: of the United States of America)?$",
    r"^PNAS$",
    r"^Nature Geoscience$",
    r"^Nature Water$",
    r"^Nature Climate Change$",
    r"^Nature Communications$",
    r"^Nature Sustainability$",
    r"^Communications Earth & Environment$",
    r"^Science Advances$",
    r"^Journal of Geophysical Research(?:: .+)?$",
    r"^Geophysical Research Letters$",
    r"^Water Resources Research$",
    r"^Reviews of Geophysics$",
    r"^Earth's Future$",
    r"^Journal of Advances in Modeling Earth Systems$",
    r"^Journal of Hydrometeorology$",
    r"^Journal of Climate$",
    r"^Bulletin of the American Meteorological Society$",
    r"^Climate Dynamics$",
    r"^Hydrology and Earth System Sciences$",
    r"^Hydrological Processes$",
    r"^Journal of Hydrology$",
    r"^Advances in Water Resources$",
    r"^Water Resources Management$",
    r"^Geoscientific Model Development$",
    r"^Earth System Science Data$",
    r"^Earth System Dynamics$",
    r"^Earth Surface Dynamics$",
    r"^The Cryosphere$",
    r"^Biogeosciences$",
    r"^Natural Hazards and Earth System Sciences$",
    r"^Natural Hazards$",
    r"^Remote Sensing of Environment$",
    r"^Remote Sensing$",
    r"^IEEE Transactions on Geoscience and Remote Sensing$",
    r"^ISPRS Journal of Photogrammetry and Remote Sensing$",
    r"^Earth and Planetary Science Letters$",
    r"^Geology$",
    r"^Geophysical Journal International$",
    r"^Journal of Glaciology$",
    r"^Environmental Research Letters$",
    r"^Global Environmental Change$",
    r"^Global Change Biology$",
    r"^Geomorphology$",
    r"^Journal of Flood Risk Management$",
]
ALLOWED_JOURNAL_RE = [re.compile(pattern, re.IGNORECASE) for pattern in ALLOWED_JOURNAL_PATTERNS]

OUTPUT = Path("assets/data/paper-radar.json")
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
CROSSREF_ENDPOINT = "https://api.crossref.org/works"
WINDOW_DAYS = 30
RESULTS_PER_KEYWORD = 20
LOCAL_TZ = ZoneInfo("Asia/Shanghai")
USER_AGENT = "GeoWater-Paper-Radar/2.1 (https://geowaterpku.github.io/)"

DATE_META_KEYS = {
    "citation_publication_date",
    "citation_online_date",
    "prism.publicationdate",
    "dc.date",
    "dc.date.issued",
    "article:published_time",
    "date",
    "citation_date",
}
JOURNAL_META_KEYS = {"citation_journal_title", "prism.publicationname", "dc.source"}
DOI_META_KEYS = {"citation_doi", "dc.identifier"}
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


def utc_now():
    return datetime.now(timezone.utc)


def iso_z(value):
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_title(title):
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def normalize_journal(value):
    return re.sub(r"\s+", " ", (value or "").replace("…", "").strip())


def stable_id(title, doi=""):
    basis = (doi or "").lower().strip() or normalize_title(title)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def parse_iso_date(value):
    if not value:
        return None
    text = str(value).strip()
    match = re.search(r"\b((?:19|20)\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", text)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def date_from_parts(container):
    if not isinstance(container, dict):
        return None
    parts_list = container.get("date-parts")
    if not isinstance(parts_list, list) or not parts_list or not parts_list[0]:
        return None
    parts = parts_list[0]
    if len(parts) < 3:
        return None
    try:
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (TypeError, ValueError):
        return None


def is_allowed_journal(journal):
    candidate = normalize_journal(journal)
    return bool(candidate) and any(pattern.fullmatch(candidate) for pattern in ALLOWED_JOURNAL_RE)


def load_existing():
    if not OUTPUT.exists():
        return {"papers": [], "crawlHistory": {}}
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {"papers": [], "crawlHistory": {}}
    except (OSError, json.JSONDecodeError):
        return {"papers": [], "crawlHistory": {}}


def extract_authors(publication_info):
    publication_info = publication_info or {}
    names = []
    for author in publication_info.get("authors") or []:
        name = (author.get("name") if isinstance(author, dict) else str(author)) or ""
        name = name.strip()
        if name:
            names.append(name)
    if names:
        return ", ".join(names)
    summary = (publication_info.get("summary") or "").strip()
    return summary.split(" - ", 1)[0].strip() if " - " in summary else ""


def crossref_authors(item):
    if not isinstance(item, dict):
        return ""
    names = []
    for author in item.get("author") or []:
        if not isinstance(author, dict):
            continue
        name = " ".join(
            part for part in ((author.get("given") or "").strip(), (author.get("family") or "").strip()) if part
        )
        if name:
            names.append(name)
    return ", ".join(names)


def select_link(result):
    link = (result.get("link") or "").strip()
    if link:
        return link
    for resource in result.get("resources") or []:
        if isinstance(resource, dict):
            link = (resource.get("link") or "").strip()
            if link:
                return link
    return ""


def extract_doi_from_text(value):
    if not value:
        return ""
    match = DOI_RE.search(str(value))
    return match.group(0).rstrip(").,;").lower() if match else ""


def extract_result_doi(result):
    candidates = [
        result.get("link"),
        result.get("snippet"),
        (result.get("publication_info") or {}).get("summary"),
    ]
    for resource in result.get("resources") or []:
        if isinstance(resource, dict):
            candidates.extend([resource.get("link"), resource.get("title")])
    for candidate in candidates:
        doi = extract_doi_from_text(candidate)
        if doi:
            return doi
    return ""


def fetch_keyword(keyword, api_key, target_year):
    response = requests.get(
        SERPAPI_ENDPOINT,
        params={
            "engine": "google_scholar",
            "q": KEYWORD_QUERIES[keyword],
            "hl": "en",
            "scisbd": "2",
            "as_ylo": str(target_year),
            "as_yhi": str(target_year),
            "as_sdt": "0",
            "num": str(RESULTS_PER_KEYWORD),
            "api_key": api_key,
        },
        timeout=45,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    return payload.get("organic_results") or []


def crossref_request(url, params=None):
    response = requests.get(
        url,
        params=params,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=25,
    )
    response.raise_for_status()
    return response.json()


def crossref_by_doi(doi):
    if not doi:
        return None
    try:
        payload = crossref_request(f"{CROSSREF_ENDPOINT}/{quote(doi, safe='')}")
        message = payload.get("message")
        return message if isinstance(message, dict) else None
    except Exception:
        return None


def title_similarity(left, right):
    return SequenceMatcher(None, normalize_title(left), normalize_title(right)).ratio()


def crossref_by_title(title, target_date):
    params = {
        "query.title": title,
        "filter": f"from-pub-date:{target_date.isoformat()},until-pub-date:{target_date.isoformat()}",
        "rows": "5",
        "select": "DOI,title,container-title,published-online,published-print,published,issued,URL,type,author",
    }
    try:
        payload = crossref_request(CROSSREF_ENDPOINT, params=params)
    except Exception:
        return None
    items = ((payload.get("message") or {}).get("items") or [])
    best = None
    best_score = 0.0
    for item in items:
        if not isinstance(item, dict):
            continue
        titles = item.get("title") or []
        candidate = titles[0] if titles else ""
        score = title_similarity(title, candidate)
        if score > best_score:
            best, best_score = item, score
    return best if best is not None and best_score >= 0.86 else None


def crossref_publication_date(item):
    if not isinstance(item, dict):
        return None, ""
    for key in ("published-online", "published", "issued", "published-print"):
        value = date_from_parts(item.get(key))
        if value:
            return value, f"crossref:{key}"
    return None, ""


def crossref_journal(item):
    if not isinstance(item, dict):
        return ""
    titles = item.get("container-title") or []
    return normalize_journal(titles[0]) if titles else ""


def meta_content(soup, keys):
    wanted = {key.lower() for key in keys}
    for meta in soup.find_all("meta"):
        key = (meta.get("name") or meta.get("property") or "").strip().lower()
        if key in wanted:
            value = (meta.get("content") or "").strip()
            if value:
                return value
    return ""


def jsonld_nodes(node):
    if isinstance(node, dict):
        yield node
        graph = node.get("@graph")
        if isinstance(graph, list):
            for child in graph:
                yield from jsonld_nodes(child)
    elif isinstance(node, list):
        for child in node:
            yield from jsonld_nodes(child)


def fetch_publisher_metadata(link):
    if not link:
        return {}
    try:
        response = requests.get(
            link,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=20,
            allow_redirects=True,
        )
        response.raise_for_status()
    except Exception:
        return {}

    soup = BeautifulSoup(response.text, "html.parser")
    result = {
        "publicationDate": parse_iso_date(meta_content(soup, DATE_META_KEYS)),
        "journal": normalize_journal(meta_content(soup, JOURNAL_META_KEYS)),
        "doi": extract_doi_from_text(meta_content(soup, DOI_META_KEYS)),
        "link": response.url,
        "dateSource": "publisher-meta",
    }
    if result["publicationDate"] and result["journal"] and result["doi"]:
        return result

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        for node in jsonld_nodes(data):
            if not result["publicationDate"]:
                result["publicationDate"] = parse_iso_date(node.get("datePublished"))
            if not result["journal"]:
                part = node.get("isPartOf")
                if isinstance(part, dict):
                    result["journal"] = normalize_journal(part.get("name") or "")
            if not result["doi"]:
                result["doi"] = extract_doi_from_text(node.get("identifier"))
    return result


def enrich_result(result, target_date):
    title = (result.get("title") or "").strip()
    publication_info = result.get("publication_info") or {}
    scholar_authors = extract_authors(publication_info)
    link = select_link(result)
    doi = extract_result_doi(result)

    crossref_item = crossref_by_doi(doi) if doi else None
    if crossref_item is None:
        crossref_item = crossref_by_title(title, target_date)

    publication_date, date_source = crossref_publication_date(crossref_item)
    journal = crossref_journal(crossref_item)
    authors = crossref_authors(crossref_item) or scholar_authors

    if isinstance(crossref_item, dict):
        crossref_doi = (crossref_item.get("DOI") or "").strip().lower()
        if crossref_doi:
            doi = crossref_doi

    publisher = {}
    if publication_date != target_date or not journal:
        publisher = fetch_publisher_metadata(link)
        publisher_date = publisher.get("publicationDate")
        if publisher_date:
            publication_date = publisher_date
            date_source = publisher.get("dateSource") or "publisher-meta"
        if publisher.get("journal"):
            journal = publisher["journal"]
        if not doi and publisher.get("doi"):
            doi = publisher["doi"]

    if publication_date != target_date or not is_allowed_journal(journal):
        return None

    canonical_link = f"https://doi.org/{doi}" if doi else (publisher.get("link") or link)
    if not canonical_link:
        return None

    return {
        "id": stable_id(title, doi),
        "title": title,
        "journal": journal,
        "authors": authors,
        "link": canonical_link,
        "doi": doi,
        "publicationDate": target_date.isoformat(),
        "datePrecision": "day",
        "dateSource": date_source,
    }


def paper_key(paper):
    doi = (paper.get("doi") or "").strip().lower()
    return f"doi:{doi}" if doi else f"title:{normalize_title(paper.get('title') or '')}"


def main():
    api_key = os.environ.get("PAPER_RADAR_SERPAPI_KEY", "").strip()
    if not api_key:
        print("PAPER_RADAR_SERPAPI_KEY is not configured; keeping the current Paper Radar snapshot.")
        return 0

    now = utc_now()
    target_date = datetime.now(LOCAL_TZ).date() - timedelta(days=1)
    cutoff_date = target_date - timedelta(days=WINDOW_DAYS - 1)
    existing = load_existing()

    papers_by_key = {}
    for paper in existing.get("papers") or []:
        publication_date = parse_iso_date(paper.get("publicationDate"))
        if not publication_date or not (cutoff_date <= publication_date <= target_date):
            continue
        if paper.get("datePrecision") != "day":
            continue
        key = paper_key(paper)
        if key not in {"doi:", "title:"}:
            papers_by_key[key] = paper

    errors = []
    scanned = 0
    yesterday_matches = {}

    for keyword in KEYWORDS:
        try:
            results = fetch_keyword(keyword, api_key, target_date.year)
        except Exception as exc:
            errors.append(f"{keyword}: {exc}")
            continue

        for result in results:
            scanned += 1
            title = (result.get("title") or "").strip()
            if not title or title.upper().startswith("[CITATION]"):
                continue
            try:
                enriched = enrich_result(result, target_date)
            except Exception as exc:
                errors.append(f"{keyword} / {title[:80]}: {exc}")
                continue
            if not enriched:
                continue

            key = paper_key(enriched)
            paper = yesterday_matches.get(key)
            if paper is None:
                enriched["matchedKeywords"] = [keyword]
                yesterday_matches[key] = enriched
            else:
                paper["matchedKeywords"] = sorted(set(paper.get("matchedKeywords") or []) | {keyword})

    if scanned == 0 and errors:
        print("All Paper Radar searches failed; retaining the previous snapshot.", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    yesterday = target_date.isoformat()
    papers_by_key = {
        key: paper for key, paper in papers_by_key.items()
        if paper.get("publicationDate") != yesterday
    }
    papers_by_key.update(yesterday_matches)

    retained = sorted(
        papers_by_key.values(),
        key=lambda paper: (paper.get("publicationDate", ""), paper.get("title", "").lower()),
        reverse=True,
    )

    history = existing.get("crawlHistory")
    if not isinstance(history, dict):
        history = {}
    history[yesterday] = {
        "status": "success",
        "crawledAt": iso_z(now),
        "paperCount": len(yesterday_matches),
        "scannedScholarResults": scanned,
        "errors": errors[:20],
    }
    history = {
        key: value for key, value in history.items()
        if parse_iso_date(key) and cutoff_date <= parse_iso_date(key) <= target_date
    }

    data = {
        "generatedAt": iso_z(now),
        "timezone": "Asia/Shanghai",
        "targetDate": yesterday,
        "windowDays": WINDOW_DAYS,
        "keywords": KEYWORDS,
        "journalFilter": {
            "mode": "allowlist",
            "description": (
                "Curated geoscience, hydrology, climate and Earth-observation journals, "
                "plus Nature, Science and PNAS."
            ),
        },
        "crawlHistory": history,
        "papers": retained,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Paper Radar updated for {yesterday}: "
        f"{len(yesterday_matches)} verified papers from {scanned} Scholar results."
    )
    for error in errors:
        print(f"Warning - {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())