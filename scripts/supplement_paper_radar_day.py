#!/usr/bin/env python3
import json
import time
from datetime import datetime, timedelta

from backfill_paper_radar import (
    BACKFILL_VERSION,
    CROSSREF_TITLE_QUERIES,
    crossref_backfill_request,
    item_to_paper,
    keyword_matches_title,
    merge_paper,
)
from update_paper_radar import (
    KEYWORDS,
    LOCAL_TZ,
    OUTPUT,
    WINDOW_DAYS,
    iso_z,
    load_existing,
    paper_key,
    parse_iso_date,
    utc_now,
)

ROWS_PER_KEYWORD = 300
QUERY_PAUSE_SECONDS = 1.5


def main():
    existing = load_existing()
    target_date = datetime.now(LOCAL_TZ).date() - timedelta(days=1)
    target_day = target_date.isoformat()
    cutoff_date = target_date - timedelta(days=WINDOW_DAYS - 1)

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
    added_or_matched = 0

    for index, keyword in enumerate(KEYWORDS):
        if index:
            time.sleep(QUERY_PAUSE_SECONDS)
        params = {
            "query.title": CROSSREF_TITLE_QUERIES[keyword],
            "filter": f"from-pub-date:{target_day},until-pub-date:{target_day}",
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
            if not paper or paper.get("publicationDate") != target_day:
                continue
            if not keyword_matches_title(keyword, paper.get("title") or ""):
                continue
            merge_paper(papers, paper, keyword)
            added_or_matched += 1

    retained = sorted(
        papers.values(),
        key=lambda paper: (paper.get("publicationDate", ""), paper.get("title", "").lower()),
        reverse=True,
    )

    target_count = sum(1 for paper in retained if paper.get("publicationDate") == target_day)

    history = existing.get("crawlHistory")
    if not isinstance(history, dict):
        history = {}
    previous = history.get(target_day) if isinstance(history.get(target_day), dict) else {}
    history[target_day] = {
        "status": previous.get("status") or "success",
        "source": "google-scholar+crossref",
        "crawledAt": iso_z(utc_now()),
        "paperCount": target_count,
        "scannedScholarResults": previous.get("scannedScholarResults", 0),
        "scannedCrossrefResults": scanned,
        "errors": list(previous.get("errors") or [])[:10],
        "supplementErrors": errors[:10],
    }

    expected_days = [
        (target_date - timedelta(days=offset)).isoformat()
        for offset in range(WINDOW_DAYS)
    ]
    all_history_complete = all(
        isinstance(history.get(day), dict) and history[day].get("status") == "success"
        for day in expected_days
    )

    now = utc_now()
    data = dict(existing)
    data.update(
        {
            "generatedAt": iso_z(now),
            "timezone": "Asia/Shanghai",
            "targetDate": target_day,
            "windowDays": WINDOW_DAYS,
            "crawlHistory": {
                day: history[day]
                for day in reversed(expected_days)
                if day in history
            },
            "papers": retained,
        }
    )
    if all_history_complete:
        data["backfillVersion"] = BACKFILL_VERSION
        data["backfillCompletedAt"] = existing.get("backfillCompletedAt") or iso_z(now)
        data["backfillRange"] = {
            "from": cutoff_date.isoformat(),
            "to": target_day,
        }
        if "backfillStats" not in data:
            data["backfillStats"] = {
                "status": "complete",
                "errors": [],
            }

    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Paper Radar Crossref supplement for {target_day}: "
        f"{target_count} total papers on target day, {scanned} candidates scanned, "
        f"{added_or_matched} relevant matches, {len(errors)} errors."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
