#!/usr/bin/env python3
"""Enrich Paper Radar entries with short Chinese research guides.

The script deliberately stores only the generated Chinese guide, not the source
abstract. Existing summaries are treated as a cache and are only regenerated
when they are missing or use an older prompt version. Abstract retrieval order
is Crossref -> OpenAlex -> publisher metadata -> title-only fallback.
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
LLM_TIMEOUT = 35
LLM_RETRY_TIMEOUT = 70
LLM_MAX_ATTEMPTS = 3
LLM_PACING_SECONDS = 1.5
MAX_ABSTRACT_CHARS = 12000
DEFAULT_MAX_PER_RUN = 120
MAX_CONSECUTIVE_FAILURES = 3
SUMMARY_PROMPT_VERSION = 2


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


def request_chat_once(url, headers, payload, timeout):
    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if response.ok:
        return response

    body = response.text[:1000]
    if response.status_code == 400 and "max_tokens" in body and "max_completion_tokens" not in payload:
        retry_payload = dict(payload)
        retry_payload["max_completion_tokens"] = retry_payload.pop("max_tokens", 420)
        retry = requests.post(url, headers=headers, json=retry_payload, timeout=timeout)
        if retry.ok:
            return retry
        response = retry
        body = retry.text[:1000]

    if response.status_code not in {408, 409, 425, 429, 500, 502, 503, 504}:
        raise RuntimeError(f"LLM HTTP {response.status_code}: {body}")
    raise requests.HTTPError(f"retryable LLM HTTP {response.status_code}: {body}", response=response)


def post_chat_completion(url, headers, payload):
    last_error = None
    for attempt in range(1, LLM_MAX_ATTEMPTS + 1):
        timeout = LLM_TIMEOUT if attempt == 1 else LLM_RETRY_TIMEOUT
        try:
            return request_chat_once(url, headers, payload, timeout)
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            last_error = exc
            if attempt >= LLM_MAX_ATTEMPTS:
                break
            backoff = 4 * attempt
            print(f"LLM request attempt {attempt} failed; retrying after {backoff}s: {exc}")
            time.sleep(backoff)
    raise RuntimeError(f"LLM request failed after {LLM_MAX_ATTEMPTS} attempts: {last_error}")


def generate_summary_zh(paper, source_text, source_name, api_key, base_url, model):
    title = normalize_space(paper.get("title"))
    journal = normalize_space(paper.get("journal"))

    if source_name == "title-only":
        evidence = "未获取到可靠英文摘要。只能依据论文标题概括研究主题。"
        user_prompt = f"""论文标题：{title}
期刊：{journal}

{evidence}

请写一段 60–100 个中文字的中文导读，目标是让地球科学相关研究人员或研究生快速明白“这篇论文大概在研究什么、为什么值得关注”。

写作要求：
1. 开头直接用容易理解的中文说清研究对象或核心问题，不要照着英文标题逐词翻译。
2. 可以保留必要的专业术语，但尽量用常用中文解释；不要堆砌术语、缩写和名词。
3. 因为没有可靠摘要，不得猜测具体数据、模型、实验设计、定量结果或研究结论。
4. 语言要像专业研究者向跨方向同行解释论文，而不是像机器翻译、新闻宣传或论文摘要。
5. 只输出一段中文，不要标题、列表、Markdown，也不要写“本文”“该研究”之外的套话。"""
    else:
        user_prompt = f"""论文标题：{title}
期刊：{journal}
摘要来源：{source_name}
英文摘要：
{source_text}

请把这篇论文写成一段 100–180 个中文字的中文研究导读。目标不是翻译摘要，而是让地球科学、水文学、遥感、气候与洪水研究相关的研究人员或研究生，在 30 秒内理解“研究为什么重要、怎么做、发现了什么”。

内容优先级：
1. 先用 1 句话说清楚：这项研究在解决什么问题，以及这个问题为什么值得关注。
2. 再用 1 句话说明：作者主要用了什么数据、方法或分析思路。只保留理解结论真正必要的方法信息，不要罗列技术细节。
3. 最后用 1–2 句话说清楚：最重要的发现是什么，以及它对水文过程、气候变化、洪水风险、遥感观测或相关决策有什么意义。只有摘要明确支持时才写应用或政策意义。

写作风格：
- 专业但易懂。术语必须准确，但优先使用自然、常见的中文表达。
- 对关键专业概念，第一次出现时如果可能影响理解，可顺手用几个字解释其含义，而不是继续堆术语。
- 多用短句和清晰的因果关系，少用连续的“基于……通过……构建……实现……”式长句。
- 尽量回答“它做了什么、发现了什么、为什么重要”，不要把导读写成方法清单。
- 有明确数字、时间范围、空间范围或变化方向时，优先保留最能帮助理解结论的 1–2 个关键信息。
- 不逐句翻译英文摘要，不使用空泛的“具有重要意义”“提供新视角”等套话，除非后面明确说明具体意义是什么。
- 不添加英文摘要没有的信息，不夸大因果关系，不把相关性写成因果。

只输出一段连贯中文，不要标题、列表或 Markdown。"""

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一名地球科学与水文学领域的资深学术编辑，擅长把专业论文解释给相邻研究方向的科研人员和研究生。"
                    "你的中文必须同时满足两点：第一，科学上准确，术语、方向、因果和定量信息不能失真；第二，读起来容易理解，"
                    "避免摘要腔、翻译腔和术语堆砌。你应优先提炼研究问题、核心方法、关键发现和具体意义，而不是复述原摘要。"
                    "当一个技术术语不是理解结论所必需时，可以省略；当必须保留时，尽量用自然中文或简短解释帮助理解。"
                    "严格区分证据与推断，没有证据时绝不补充具体方法、结果、机制、因果或政策含义。"
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 520,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    response = post_chat_completion(chat_completions_url(base_url), headers, payload)
    return extract_llm_content(response.json())


def summary_needs_refresh(paper):
    if not normalize_space(paper.get("summaryZh")):
        return True
    try:
        version = int(paper.get("summaryPromptVersion") or 0)
    except (TypeError, ValueError):
        version = 0
    return version < SUMMARY_PROMPT_VERSION


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

    candidates = [paper for paper in papers if isinstance(paper, dict) and summary_needs_refresh(paper)]
    candidates.sort(key=lambda paper: (paper.get("publicationDate") or "", paper.get("title") or ""), reverse=True)
    candidates = candidates[:max_per_run]

    if not candidates:
        print(f"All Paper Radar entries already use Chinese guide prompt v{SUMMARY_PROMPT_VERSION}; no LLM calls needed.")
        return 0

    print(f"Generating or refreshing Chinese guides for {len(candidates)} Paper Radar entries with prompt v{SUMMARY_PROMPT_VERSION}.")
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
            paper["summaryPromptVersion"] = SUMMARY_PROMPT_VERSION
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
        time.sleep(LLM_PACING_SECONDS)

    if changed:
        payload["summaryPipeline"] = {
            "lastGeneratedAt": utc_now_iso(),
            "generatedThisRun": changed,
            "failedThisRun": failed,
            "sourceCounts": source_counts,
            "mode": "abstract-first-with-title-fallback",
            "promptVersion": SUMMARY_PROMPT_VERSION,
        }
        OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Saved {changed} Chinese guides with prompt v{SUMMARY_PROMPT_VERSION}; {failed} failed and will retry on a later run.")
    else:
        print(f"No Chinese guides were saved; {failed} entries failed and will retry later.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())