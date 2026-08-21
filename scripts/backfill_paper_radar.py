#!/usr/bin/env python3
import json
import re
import sys
import time
from datetime import datetime, timedelta

import requests

from update_paper_radar import (
    CROSSREF_ENDPOINT,
    KEYWORDS,
    LOCAL_TZ,
    OUTPUT,
    USER_AGENT,
    WINDOW_DAYS,
    crossref_authors,
    crossref_journal,
    crossref_publication_date,
    is_allowed_journal,
    iso_z,
    load_existing,
    paper_key,
    parse_iso_date,
    stable_id,
    utc_now,
)

BACKFILL_VERSION = 1
ROWS_PER_KEYWORD = 1000
MAX_CROSSREF_ATTEMPTS = 6
QUERY_PAUSE_SECONDS = 2.5

CROSSREF_TITLE_QUERIES = {
    "river modeling": "river modeling",
    "global hydrology": "global hydrology",
    "flood-human interaction": "flood human interaction",
    "river remote sensing": "river remote sensing",
    "hydroclimate": "hydroclimate hydroclimatic",
}


def keyword_matches_title(keyword, title):
    value = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
    if keyword == "river modeling":
        return "river" in value and re.search(r"\bmodel(?:ing|ling|led|s)?\b", value) is not None
    if keyword == "global hydrology":
        return "global" in value and "hydrolog" in value
    if keyword == "flood-human interaction":
        return "flood" in value and any(
            token in value
            for token in ("human", "people", "population", "community", "social", "societ", "urban")
        )
    if keyword == "river remote sensing":
        return "river" in value and any(
            token in value
            for token in ("remote sensing", "satellite", "earth observation", "swot")
        )
    if keyword == "hydroclimate":
        return "hydroclimat" in value or "hydroclimate" in value
    return False


def crossref_backfill_request(params):
    last_error = None
    for attempt in range(MAX_CROSSREF_ATTEMPTS):
        try:
            response = requests.get(
                CROSSREF_ENDPOINT,
                params=params,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=60,
            )
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else min(30.0, 2.0 ** (attempt + 1))
                except (TypeError, ValueError):
                    delay = min(30.0, 2.0 ** (attempt + 1))
                last_error = RuntimeError(f"Crossref rate limited request (HTTP 429); retrying after {delay:.1f}s")
                if attempt < MAX_CROSSREF_ATTEMPTS - 1:
                    time.sleep(delay)
                    continue
            if 500 <= response.status_code < 600 and attempt < MAX_CROSSREF_ATTEMPTS - 1:
                delay = min(20.0, 2.0 ** (attempt + 1))
                last_error = RuntimeError(f"Crossref server error HTTP {response.status_code}")
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            if attempt < MAX_CROSSREF_ATTEMPTS - 1:
                time.sleep(min(20.0, 2.0 ** (attempt + 1)))
                continue
            raise
    if last_error:
        raise last_error
    raise RuntimeError("Crossref request failed without a response")


def item_to_paper(item):
    if not isinstance(item, dict):
        return None
    titles = item.get("title") or []
    title = (titles[0] if titles else "").strip()
    publication_date, date_source = crossref_publication_date(item)
    journal = crossref_journal(item)
    if not title or not publication_date or not is_allowed_journal(journal):
        return None

    doi = (item.get("DOI") or "").strip().lower()
    link = f"https://doi.org/{doi}" if doi else (item.get("URL") or "").strip()
    if not link:
        return None

    return {
        "id": stable_id(title, doi),
        "title": title,
        "journal": journal,
        "authors": crossref_authors(item),
        "link": link,
        "doi": doi,
        "publicationDate": publication_date.isoformat(),
        "datePrecision": "day",
        "dateSource": date_source,
        "matchedKeywords": [],
    }


def merge_paper(store, paper, keyword=None):
    key = paper_key(paper)
    current = store.get(key)
    if current is None:
        current = dict(paper)
        current["matchedKeywords"] = list(paper.get("matchedKeywords") or [])
        store[key] = current

    tags = set(current.get("matchedKeywords") or [])
    tags.update(paper.get("matchedKeywords") or [])
    if keyword:
        tags.add(keyword)
    current["matchedKeywords"] = sorted(tags)

    for field in (
        "title",
        "journal",
        "authors",
        "link",
        "doi",
        "publicationDate",
        "datePrecision",
        "dateSource",
    ):
        if paper.get(field):
            current[field] = paper[field]


def dates_between(start, end):
    current = start
    values = []
    while current <= end:
        values.append(current)
        current += timedelta(days=1)
    return values


def main():
    existing = load_existing()
    target_date = datetime.now(LOCAL_TZ).date() - timedelta(days=1)
    cutoff_date = target_date - timedelta(days=WINDOW_DAYS - 1)
    expected_dates = [day.isoformat() for day in dates_between(cutoff_date, target_date)]

    history = existing.get("crawlHistory")
    if not isinstance(history, dict):
        history = {}

    already_complete = (
        existing.get("backfillVersion") == BACKFILL_VERSION
        and all((history.get(day) or {}).get("status") == "success" for day in expected_dates)
    )
    if already_complete:
        print("Paper Radar 30-day backfill is already complete.")
        return 0

    papers = {}
    for paper in existing.get("papers") or []:
        publication_date = parse_iso_date(paper.get("publicationDate"))
        if (
            publication_date
            and cutoff_date <= publication_date <= target_date
            and paper.get("datePrecision") == "day"
        ):
            merge_paper(papers, paper)

    errors = []
    scanned = 0

    for index, keyword in enumerate(KEYWORDS):
        if index:
            time.sleep(QUERY_PAUSE_SECONDS)
        params = {
            "query.title": CROSSREF_TITLE_QUERIES[keyword],
            "filter": (
                f"from-pub-date:{cutoff_date.isoformat()},"
                f"until-pub-date:{target_date.isoformat()}"
            ),
            "rows": str(ROWS_PER_KEYWORD),
            "select": (
                "DOI,title,container-title,published-online,published-print,"
                "published,issued,URL,type,author"
            ),
        }
        try:
            payload = crossref_backfill_request(params)
            items = ((payload.get("message") or {}).get("items") or [])
        except Exception as exc:
            errors.append(f"{keyword}: {exc}")
            continue

        scanned += len(items)
        for item in items:
            paper = item_to_paper(item)
            if not paper:
                continue
            publication_date = parse_iso_date(paper["publicationDate"])
            if not publication_date or not (cutoff_date <= publication_date <= target_date):
                continue
            if not keyword_matches_title(keyword, paper["title"]):
                continue
            merge_paper(papers, paper, keyword)

    counts = {day: 0 for day in expected_dates}
    for paper in papers.values():
        day = paper.get("publicationDate")
        if day in counts:
            counts[day] += 1

    now = utc_now()
    complete = not errors
    history_status = "success" if complete else "partial"
    for day in expected_dates:
        previous = history.get(day) if isinstance(history.get(day), dict) else {}
        source = "crossref-backfill"
        if previous.get("scannedScholarResults") is not None:
            source = "crossref-backfill+google-scholar"
        history[day] = {
            "status": history_status,
            "source": source,
            "crawledAt": iso_z(now),
            "paperCount": counts[day],
            "errors": errors[:20],
        }
        if previous.get("scannedScholarResults") is not None:
            history[day]["scannedScholarResults"] = previous["scannedScholarResults"]

    retained = sorted(
        papers.values(),
        key=lambda paper: (paper.get("publicationDate", ""), paper.get("title", "").lower()),
        reverse=True,
    )

    data = dict(existing)
    data.update(
        {
            "generatedAt": iso_z(now),
            "timezone": "Asia/Shanghai",
            "targetDate": target_date.isoformat(),
            "windowDays": WINDOW_DAYS,
            "backfillVersion": BACKFILL_VERSION if complete else existing.get("backfillVersion"),
            "backfillCompletedAt": iso_z(now) if complete else existing.get("backfillCompletedAt"),
            "backfillRange": {
                "from": cutoff_date.isoformat(),
                "to": target_date.isoformat(),
            },
            "backfillStats": {
                "scannedCrossrefResults": scanned,
                "errors": errors[:20],
            },
            "crawlHistory": {day: history[day] for day in expected_dates},
            "papers": retained,
        }
    )

    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Paper Radar backfill {cutoff_date.isoformat()} to {target_date.isoformat()}: "
        f"{len(retained)} verified papers from {scanned} Crossref candidates; "
        f"{len(errors)} query errors."
    )
    for error in errors:
        print(f"Backfill warning - {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
