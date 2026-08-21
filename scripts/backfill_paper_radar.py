#!/usr/bin/env python3
import json
import re
import sys
from datetime import datetime, timedelta

from update_paper_radar import (
    CROSSREF_ENDPOINT,
    KEYWORDS,
    LOCAL_TZ,
    OUTPUT,
    WINDOW_DAYS,
    crossref_authors,
    crossref_journal,
    crossref_publication_date,
    crossref_request,
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

    for keyword in KEYWORDS:
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
            payload = crossref_request(CROSSREF_ENDPOINT, params=params)
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
