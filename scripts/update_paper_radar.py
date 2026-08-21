#!/usr/bin/env python3
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

KEYWORDS = [
    "river modeling",
    "global hydrology",
    "flood-human interaction",
    "river remote sensing",
    "hydroclimate",
]

OUTPUT = Path("assets/data/paper-radar.json")
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
WINDOW_DAYS = 30
RESULTS_PER_KEYWORD = 20


def utc_now():
    return datetime.now(timezone.utc)


def iso_z(value):
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_title(title):
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def stable_id(title):
    return hashlib.sha1(normalize_title(title).encode("utf-8")).hexdigest()[:16]


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_existing():
    if not OUTPUT.exists():
        return {"papers": []}
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"papers": []}


def extract_authors(publication_info):
    authors = publication_info.get("authors") or []
    names = []
    for author in authors:
        if isinstance(author, dict):
            name = (author.get("name") or "").strip()
        else:
            name = str(author).strip()
        if name:
            names.append(name)
    if names:
        return ", ".join(names)

    summary = (publication_info.get("summary") or "").strip()
    if " - " in summary:
        return summary.split(" - ", 1)[0].strip()
    return ""


def extract_journal(publication_info):
    summary = (publication_info.get("summary") or "").strip()
    parts = [part.strip() for part in summary.split(" - ") if part.strip()]
    if len(parts) < 2:
        return ""

    venue = parts[1]
    venue = re.sub(r",?\s*(?:19|20)\d{2}(?:\b.*)?$", "", venue).strip(" ,")
    if venue:
        return venue

    if len(parts) >= 3:
        return parts[2]
    return ""


def select_link(result):
    link = (result.get("link") or "").strip()
    if link:
        return link

    for resource in result.get("resources") or []:
        if isinstance(resource, dict):
            resource_link = (resource.get("link") or "").strip()
            if resource_link:
                return resource_link
    return ""


def fetch_keyword(keyword, api_key, current_year):
    response = requests.get(
        SERPAPI_ENDPOINT,
        params={
            "engine": "google_scholar",
            "q": keyword,
            "hl": "en",
            "scisbd": "2",
            "as_ylo": str(current_year - 1),
            "as_sdt": "0",
            "num": str(RESULTS_PER_KEYWORD),
            "api_key": api_key,
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    return payload.get("organic_results") or []


def main():
    api_key = os.environ.get("PAPER_RADAR_SERPAPI_KEY", "").strip()
    if not api_key:
        print("PAPER_RADAR_SERPAPI_KEY is not configured; keeping the current Paper Radar snapshot.")
        return 0

    now = utc_now()
    cutoff = now - timedelta(days=WINDOW_DAYS)
    existing = load_existing()
    valid_keywords = set(KEYWORDS)

    papers_by_title = {}
    for paper in existing.get("papers") or []:
        title = (paper.get("title") or "").strip()
        if not title:
            continue
        key = normalize_title(title)
        if not key:
            continue

        # Remove retired search labels while preserving papers that still belong
        # to at least one active radar theme. If a paper is rediscovered under
        # the new "river modeling" query below, that label will be added back.
        paper["matchedKeywords"] = [
            keyword
            for keyword in (paper.get("matchedKeywords") or [])
            if keyword in valid_keywords
        ]
        papers_by_title[key] = paper

    errors = []
    seen_this_run = set()

    for keyword in KEYWORDS:
        try:
            results = fetch_keyword(keyword, api_key, now.year)
        except Exception as exc:
            errors.append(f"{keyword}: {exc}")
            continue

        for result in results:
            title = (result.get("title") or "").strip()
            if not title or title.upper().startswith("[CITATION]"):
                continue

            key = normalize_title(title)
            if not key:
                continue

            link = select_link(result)
            if not link:
                continue

            publication_info = result.get("publication_info") or {}
            authors = extract_authors(publication_info)
            journal = extract_journal(publication_info)

            existing_paper = papers_by_title.get(key)
            if existing_paper:
                matched = set(existing_paper.get("matchedKeywords") or [])
                matched.add(keyword)
                existing_paper.update({
                    "title": title,
                    "authors": authors or existing_paper.get("authors", ""),
                    "journal": journal or existing_paper.get("journal", ""),
                    "link": link,
                    "lastSeenAt": iso_z(now),
                    "matchedKeywords": sorted(matched),
                })
            else:
                papers_by_title[key] = {
                    "id": stable_id(title),
                    "title": title,
                    "journal": journal,
                    "authors": authors,
                    "link": link,
                    "firstSeenAt": iso_z(now),
                    "lastSeenAt": iso_z(now),
                    "matchedKeywords": [keyword],
                }
            seen_this_run.add(key)

    if not seen_this_run and errors:
        print("All Paper Radar searches failed; retaining the previous snapshot.", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    retained = []
    for paper in papers_by_title.values():
        matched_keywords = [
            keyword
            for keyword in (paper.get("matchedKeywords") or [])
            if keyword in valid_keywords
        ]
        if not matched_keywords:
            continue
        paper["matchedKeywords"] = matched_keywords

        first_seen = parse_date(paper.get("firstSeenAt"))
        if first_seen is None:
            first_seen = now
            paper["firstSeenAt"] = iso_z(now)
        if first_seen >= cutoff:
            retained.append(paper)

    retained.sort(
        key=lambda paper: (
            parse_date(paper.get("firstSeenAt")) or datetime.min.replace(tzinfo=timezone.utc),
            paper.get("title", "").lower(),
        ),
        reverse=True,
    )

    data = {
        "generatedAt": iso_z(now),
        "windowDays": WINDOW_DAYS,
        "keywords": KEYWORDS,
        "papers": retained,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Paper Radar updated: {len(retained)} unique papers retained.")
    for error in errors:
        print(f"Warning - {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
