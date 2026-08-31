#!/usr/bin/env python3
"""Enrich Paper Radar entries with short Chinese research guides.

The script deliberately stores only the generated Chinese guide, not the source
abstract. Existing summaries are treated as a cache and are never regenerated
unless they are empty. Abstract retrieval order is Crossref -> OpenAlex ->
publisher metadata -> title-only fallback.
"""

import html
import json
import os
import re
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

OUTPUT = Path("assets/data/paper-radar.json")
CROSSREF_WORKS = "https://api.crossref.org/works"
OPENALEX_WORKS = "https://api.openalex.org/works"
USER_AGENT = "GeoWater-Paper-Radar/3.0 (https://geowaterpku.github.io/)"
HTTP_TIMEOUT = 12
PUBLISHER_TIMEOUT = 8
LLM_TIMEOUT = 30
MAX_ABSTRACT_CHARS = 12000
DEFAULT_MAX_PER_RUN = 120
MAX_CONSECUTIVE_FAILURES = 3


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_space(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_title(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def clean_rich_text(value):
    if not value:
        return ""
    text = html.unescape(str(value))
    text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    text = normalize_space(text)
    return text[:MAX_ABSTRACT_CHARS]


def usable_abstract(value, title=""):
    text = clean_rich_text(value)
    if len(text) < 100:
        return ""
    if normalize_title(text) == normalize_title(title):
        return ""
    lowered = text.lower()
    generic_markers = (
        "enable javascript",
        "access denied",
        "cookie policy",
        "all rights reserved",
        "page not found",
    )
    if any(marker in lowered for marker in generic_markers):
        return ""
    return text


def request_json(url, *, params=None, headers=None, timeout=HTTP_TIMEOUT):
    merged_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    if headers:
        merged_headers.update(headers)
    response = requests.get(url, params=params, headers=merged_headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def crossref_abstract(paper):
    doi = normalize_space(paper.get("doi"))
    if not doi:
        return "", ""
    try:
        payload = request_json(f"{CROSSREF_WORKS}/{quote(doi, safe='')}")
        message = payload.get("message") or {}
        abstract = usable_abstract(message.get("abstract"), paper.get("title"))
        if abstract:
            return abstract, "crossref-abstract"
    except Exception as exc:
        print(f"Crossref abstract unavailable for {doi}: {exc}")
    return "", ""


def decode_openalex_abstract(index):
    if not isinstance(index, dict) or not index:
        return ""
    positioned = []
    for word, positions in index.items():
        if not isinstance(positions, list):
            continue
        for position in positions:
            try:
                positioned.append((int(position), word))
            except (TypeError, ValueError):
                continue
    positioned.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positioned)


def openalex_work_for_paper(paper):
    doi = normalize_space(paper.get("doi"))
    title = normalize_space(paper.get("title"))
    if doi:
        try:
            return request_json(f"{OPENALEX_WORKS}/https://doi.org/{quote(doi, safe='/')}")
        except Exception as exc:
            print(f"OpenAlex DOI lookup unavailable for {doi}: {exc}")

    if not title:
        return None
    try:
        payload = request_json(
            OPENALEX_WORKS,
            params={"search": title, "per-page": 5},
        )
    except Exception as exc:
        print(f"OpenAlex title lookup unavailable for {title[:70]}: {exc}")
        return None

    best = None
    best_score = 0.0
    for item in payload.get("results") or []:
        candidate = normalize_space(item.get("title"))
        score = SequenceMatcher(None, normalize_title(title), normalize_title(candidate)).ratio()
        if score > best_score:
            best, best_score = item, score
    return best if best is not None and best_score >= 0.88 else None


def openalex_abstract(paper):
    item = openalex_work_for_paper(paper)
    if not isinstance(item, dict):
        return "", ""
    abstract = usable_abstract(
        decode_openalex_abstract(item.get("abstract_inverted_index")),
        paper.get("title"),
    )
    return (abstract, "openalex-abstract") if abstract else ("", "")


def jsonld_nodes(value):
    if isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if isinstance(graph, list):
            for child in graph:
                yield from jsonld_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from jsonld_nodes(child)


def publisher_abstract(paper):
    link = normalize_space(paper.get("link"))
    if not link:
        return "", ""
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
            timeout=PUBLISHER_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()
    except Exception as exc:
        print(f"Publisher metadata unavailable for {link}: {exc}")
        return "", ""

    soup = BeautifulSoup(response.text, "html.parser")
    wanted = {
        "citation_abstract",
        "dc.description",
        "dcterms.abstract",
        "description",
        "og:description",
        "twitter:description",
    }
    for meta in soup.find_all("meta"):
        key = normalize_space(meta.get("name") or meta.get("property")).lower()
        if key not in wanted:
            continue
        abstract = usable_abstract(meta.get("content"), paper.get("title"))
        if abstract:
            return abstract, "publisher-description"

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        for node in jsonld_nodes(data):
            abstract = usable_abstract(
                node.get("abstract") or node.get("description"),
                paper.get("title"),
            )
            if abstract:
                return abstract, "publisher-jsonld"
    return "", ""


def get_summary_source_text(paper):
    for fetcher in (crossref_abstract, openalex_abstract, publisher_abstract):
        abstract, source = fetcher(paper)
        if abstract:
            return abstract, source
    return "", "title-only"


def chat_completions_url(base_url):
    base = normalize_space(base_url).rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def extract_llm_content(payload):
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("LLM response has no choices")
    content = ((choices[0].get("message") or {}).get("content"))
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") in {"text", "output_text"}:
                parts.append(str(part.get("text") or ""))
        content = "".join(parts)
    content = normalize_space(content)
    if not content:
        raise RuntimeError("LLM response content is empty")
    content = re.sub(r"^(?:中文导读|导读|摘要)\s*[：:]\s*", "", content)
    content = content.strip(" \t\n\r\"'“”")
    return content


def post_chat_completion(url, headers, payload):
    response = requests.post(url, headers=headers, json=payload, timeout=LLM_TIMEOUT)
    if response.ok:
        return response

    # Some newer OpenAI-compatible endpoints accept max_completion_tokens but
    # reject max_tokens. Retry once with the alternate field when indicated.
    body = response.text[:1000]
    if response.status_code == 400 and "max_tokens" in body and "max_completion_tokens" not in payload:
        retry_payload = dict(payload)
        retry_payload["max_completion_tokens"] = retry_payload.pop("max_tokens", 420)
        retry = requests.post(url, headers=headers, json=retry_payload, timeout=LLM_TIMEOUT)
        if retry.ok:
            return retry
        body = retry.text[:1000]
        raise RuntimeError(f"LLM HTTP {retry.status_code}: {body}")

    raise RuntimeError(f"LLM HTTP {response.status_code}: {body}")


def generate_summary_zh(paper, source_text, source_name, api_key, base_url, model):
    title = normalize_space(paper.get("title"))
    journal = normalize_space(paper.get("journal"))

    if source_name == "title-only":
        evidence = "未获取到可靠英文摘要。只能依据论文标题概括研究主题。"
        user_prompt = f"""论文标题：{title}\n期刊：{journal}\n\n{evidence}\n\n请生成 50–90 个中文字的中文导读。只能说明论文聚焦的研究主题、对象或问题，不得推断论文采用了什么具体数据、方法，也不得声称论文得出了某项具体结果。不要逐字翻译标题，不要编造信息。只输出一段中文。"""
    else:
        user_prompt = f"""论文标题：{title}\n期刊：{journal}\n摘要来源：{source_name}\n英文摘要：\n{source_text}\n\n请生成 80–150 个中文字的中文导读。依次交代：研究解决什么问题；主要数据/方法（摘要有明确说明时）；最重要的发现或科学意义。不要逐句翻译，不要添加英文摘要没有的信息，不要夸大结论。保持水文学、地球科学、遥感、洪水风险等专业术语准确。只输出一段中文，不要标题、列表或 Markdown。"""

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一名严谨的地球科学与水文学研究编辑。你的任务是基于给定证据生成简洁、准确、可快速扫读的中文论文导读。"
                    "严格区分证据与推断；没有证据时不要补充具体方法、结果或因果结论。"
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 420,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    response = post_chat_completion(chat_completions_url(base_url), headers, payload)
    return extract_llm_content(response.json())


def main():
    api_key = normalize_space(os.environ.get("PAPER_RADAR_LLM_API_KEY"))
    base_url = normalize_space(os.environ.get("PAPER_RADAR_LLM_BASE_URL"))
    model = normalize_space(os.environ.get("PAPER_RADAR_LLM_MODEL"))
    if not api_key or not base_url or not model:
        print("::warning::Paper Radar Chinese summaries skipped: LLM API key/base URL/model is not fully configured.")
        return 0

    if not OUTPUT.exists():
        print("::warning::Paper Radar Chinese summaries skipped: paper-radar.json does not exist.")
        return 0

    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    papers = payload.get("papers") or []
    if not isinstance(papers, list):
        raise RuntimeError("paper-radar.json papers must be a list")

    try:
        max_per_run = max(1, int(os.environ.get("PAPER_RADAR_SUMMARY_MAX_PER_RUN", DEFAULT_MAX_PER_RUN)))
    except ValueError:
        max_per_run = DEFAULT_MAX_PER_RUN

    candidates = [paper for paper in papers if isinstance(paper, dict) and not normalize_space(paper.get("summaryZh"))]
    candidates.sort(key=lambda paper: (paper.get("publicationDate") or "", paper.get("title") or ""), reverse=True)
    candidates = candidates[:max_per_run]

    if not candidates:
        print("All Paper Radar entries already have Chinese guides; no LLM calls needed.")
        return 0

    print(f"Generating Chinese guides for {len(candidates)} Paper Radar entries.")
    changed = 0
    failed = 0
    consecutive_failures = 0
    source_counts = {}

    for index, paper in enumerate(candidates, start=1):
        label = normalize_space(paper.get("doi") or paper.get("title"))[:100]
        try:
            source_text, source_name = get_summary_source_text(paper)
            summary = generate_summary_zh(paper, source_text, source_name, api_key, base_url, model)
            paper["summaryZh"] = summary
            paper["summarySource"] = source_name
            paper["summaryGeneratedAt"] = utc_now_iso()
            source_counts[source_name] = source_counts.get(source_name, 0) + 1
            changed += 1
            consecutive_failures = 0
            print(f"[{index}/{len(candidates)}] summary generated ({source_name}): {label}")
        except Exception as exc:
            failed += 1
            consecutive_failures += 1
            print(f"::warning::[{index}/{len(candidates)}] Chinese guide failed for {label}: {exc}")
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print(
                    f"::warning::Stopping summary enrichment after {MAX_CONSECUTIVE_FAILURES} consecutive failures; "
                    "unsummarized papers will retry on a later run."
                )
                break
        time.sleep(0.15)

    if changed:
        payload["summaryPipeline"] = {
            "lastGeneratedAt": utc_now_iso(),
            "generatedThisRun": changed,
            "failedThisRun": failed,
            "sourceCounts": source_counts,
            "mode": "abstract-first-with-title-fallback",
        }
        OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Saved {changed} new Chinese guides; {failed} failed and will retry on a later run.")
    else:
        print(f"No Chinese guides were saved; {failed} entries failed and will retry later.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
