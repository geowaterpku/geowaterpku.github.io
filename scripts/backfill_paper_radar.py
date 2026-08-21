#!/usr/bin/env python3
import html
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
ROWS_PER_KEYWORD = 300
MAX_CROSSREF_ATTEMPTS = 6
QUERY_PAUSE_SECONDS = 1.5
TAG_RE = re.compile(r"<[^>]+>")

CROSSREF_TITLE_QUERIES = {
    "river modeling": "river modeling",
    "global hydrology": "global hydrology",
    "flood-human interaction": "flood human interaction",
    "river remote sensing": "river remote sensing",
    "hydroclimate": "hydroclimate hydroclimatic",
}


def clean_markup_text(value):
    """Convert lightweight publisher/Crossref markup such as <scp>NFM</scp> to plain text."""
    text = str(value or "")
    # Some feeds contain encoded markup, so decode twice before removing tags.
    for _ in range(2):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    text = TAG_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def keyword_matches_title(keyword, title):
    value = re.sub(r"[^a-z0-9]+", " ", clean_markup_text(title).lower()).strip()
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
                last_error = RuntimeError(
                    f"Crossref rate limited request (HTTP 429); retrying after {delay:.1f}s"
                )
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
    title = clean_markup_text(titles[0] if titles else "")
    publication_date, date_source = crossref_publication_date(item)
    journal = clean_markup_text(crossref_journal(item))
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
        "authors": clean_markup_text(crossref_authors(item)),
        "link": link,
        "doi": doi,
        "publicationDate": publication_date.isoformat(),
        "datePrecision": "day",
        "dateSource": date_source,
        "matchedKeywords": [],
    }


def sanitize_paper(paper):
    cleaned = dict(paper)
    for field in ("title", "journal", "authors"):
        if field in cleaned:
            cleaned[field] = clean_markup_text(cleaned.get(field))
    return cleaned


def merge_paper(store, paper, keyword=None):
    paper = sanitize_paper(paper)
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

    # Daily self-healing rule: inspect all 30 days, but query only dates that are
    # missing or were not completed successfully. A successful zero-paper day is
    # a valid crawled day and should remain "无" in the UI.
    missing_dates = [
        day for day in expected_dates
        if not isinstance(history.get(day), dict) or history[day].get("status") != "success"
    ]

    papers = {}
    sanitized_changed = False
    for raw_paper in existing.get("papers") or []:
        publication_date = parse_iso_date(raw_paper.get("publicationDate"))
        if (
            publication_date
            and cutoff_date <= publication_date <= target_date
            and raw_paper.get("datePrecision") == "day"
        ):
            cleaned = sanitize_paper(raw_paper)
            if cleaned != raw_paper:
                sanitized_changed = True
            merge_paper(papers, cleaned)

    repair_errors = {}
    repair_scanned = {}

    for day_index, day in enumerate(missing_dates):
        errors = []
        scanned = 0
        for keyword_index, keyword in enumerate(KEYWORDS):
            if day_index or keyword_index:
                time.sleep(QUERY_PAUSE_SECONDS)
            params = {
                "query.title": CROSSREF_TITLE_QUERIES[keyword],
                "filter": f"from-pub-date:{day},until-pub-date:{day}",
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
                if not paper or paper.get("publicationDate") != day:
                    continue
                if not keyword_matches_title(keyword, paper.get("title") or ""):
                    continue
                merge_paper(papers, paper, keyword)

        repair_errors[day] = errors
        repair_scanned[day] = scanned

        day_count = sum(1 for paper in papers.values() if paper.get("publicationDate") == day)
        previous = history.get(day) if isinstance(history.get(day), dict) else {}
        history[day] = {
            "status": "success" if not errors else "partial",
            "source": "crossref-repair",
            "crawledAt": iso_z(utc_now()),
            "paperCount": day_count,
            "scannedCrossrefResults": scanned,
            "errors": errors[:20],
        }
        if previous.get("scannedScholarResults") is not None:
            history[day]["scannedScholarResults"] = previous["scannedScholarResults"]

    retained = sorted(
        papers.values(),
        key=lambda paper: (paper.get("publicationDate", ""), paper.get("title", "").lower()),
        reverse=True,
    )

    trimmed_history = {
        day: history[day]
        for day in expected_dates
        if isinstance(history.get(day), dict)
    }
    complete_window = all(
        isinstance(trimmed_history.get(day), dict)
        and trimmed_history[day].get("status") == "success"
        for day in expected_dates
    )

    history_changed = trimmed_history != {
        day: value for day, value in history.items() if day in expected_dates
    }
    should_write = bool(missing_dates) or sanitized_changed or history_changed

    if not should_write:
        print("Paper Radar 30-day window is complete; no repair needed.")
        return 0

    now = utc_now()
    all_errors = [error for day in missing_dates for error in repair_errors.get(day, [])]
    total_scanned = sum(repair_scanned.values())

    data = dict(existing)
    data.update(
        {
            "generatedAt": iso_z(now),
            "timezone": "Asia/Shanghai",
            "targetDate": target_date.isoformat(),
            "windowDays": WINDOW_DAYS,
            "backfillVersion": BACKFILL_VERSION if complete_window else existing.get("backfillVersion"),
            "backfillCompletedAt": (
                existing.get("backfillCompletedAt") or iso_z(now)
                if complete_window else existing.get("backfillCompletedAt")
            ),
            "backfillRange": {
                "from": cutoff_date.isoformat(),
                "to": target_date.isoformat(),
            },
            "backfillStats": {
                "mode": "daily-missing-date-repair",
                "checkedDays": WINDOW_DAYS,
                "repairedDays": missing_dates,
                "scannedCrossrefResults": total_scanned,
                "errors": all_errors[:20],
            },
            "crawlHistory": trimmed_history,
            "papers": retained,
        }
    )

    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Paper Radar checked {WINDOW_DAYS} days; repaired {len(missing_dates)} missing/partial day(s), "
        f"scanned {total_scanned} Crossref candidates, {len(all_errors)} query errors."
    )
    for day in missing_dates:
        count = sum(1 for paper in retained if paper.get("publicationDate") == day)
        state = "success" if not repair_errors.get(day) else "partial"
        print(f" - {day}: {state}, {count} paper(s)")
    for error in all_errors:
        print(f"Repair warning - {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
