#!/usr/bin/env python3
"""Enrich Paper Radar entries with concise, question-led Chinese research guides.

The script stores only the generated Chinese guide, not the source abstract.
Existing guides are refreshed when they are missing or use an older prompt
version. Abstract retrieval order is Crossref -> OpenAlex -> publisher metadata
-> title-only fallback.

Historical backfill is failure-tolerant: one paper may retry up to 10 times, and
a permanently failing paper never stops the rest of the batch.
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
LLM_MAX_ATTEMPTS = 10
LLM_PACING_SECONDS = 1.5
LLM_BACKOFF_CAP_SECONDS = 12
MAX_ABSTRACT_CHARS = 12000
DEFAULT_MAX_PER_RUN = 120
SUMMARY_PROMPT_VERSION = 3

ABSTRACT_GUIDE_LABELS = (
    "新在哪里",
    "有意思的现象",
    "怎么解释",
    "为什么重要",
)
TITLE_GUIDE_LABELS = (
    "研究什么",
    "为什么值得关注",
)
RETRYABLE_HTTP_STATUSES = {408, 409, 425, 429, 500, 502, 503, 504}


class NonRetryableLLMError(RuntimeError):
    """An LLM API error that should not be retried for the current paper."""


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
    return normalize_space(text)[:MAX_ABSTRACT_CHARS]


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
        content = "\n".join(parts)
    if content is None:
        raise RuntimeError("LLM response content is empty")

    text = html.unescape(str(content)).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"^```(?:text|markdown)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())

    lines = []
    for raw_line in text.split("\n"):
        line = normalize_space(raw_line)
        line = re.sub(r"^[\-•]\s*", "", line)
        if line:
            lines.append(line)
    if not lines:
        raise RuntimeError("LLM response content is empty")
    return "\n".join(lines)


def validate_guide(summary, source_name):
    labels = TITLE_GUIDE_LABELS if source_name == "title-only" else ABSTRACT_GUIDE_LABELS
    lines = [normalize_space(line) for line in summary.splitlines() if normalize_space(line)]
    found = set()
    for line in lines:
        for label in labels:
            if re.match(rf"^{re.escape(label)}[？?]?\s*[：:]", line):
                found.add(label)
                break
    if len(found) < len(labels):
        missing = ", ".join(label for label in labels if label not in found)
        raise RuntimeError(f"LLM guide format is incomplete; missing: {missing}")
    return summary


def request_chat_once(url, headers, payload, timeout):
    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if response.ok:
        return response

    body = response.text[:1000]
    if response.status_code == 400 and "max_tokens" in body and "max_completion_tokens" not in payload:
        retry_payload = dict(payload)
        retry_payload["max_completion_tokens"] = retry_payload.pop("max_tokens", 620)
        retry = requests.post(url, headers=headers, json=retry_payload, timeout=timeout)
        if retry.ok:
            return retry
        response = retry
        body = retry.text[:1000]

    if response.status_code in RETRYABLE_HTTP_STATUSES:
        raise requests.HTTPError(
            f"retryable LLM HTTP {response.status_code}: {body}",
            response=response,
        )
    raise NonRetryableLLMError(f"LLM HTTP {response.status_code}: {body}")


def build_summary_prompt(title, journal, source_text, source_name):
    if source_name == "title-only":
        return f"""论文标题：{title}
期刊：{journal}

目前没有获取到可靠英文摘要，因此只能依据标题做非常保守的导读。

你的任务不是猜论文结论，而是帮助研究者快速判断这篇论文大概关注什么。请严格输出下面 2 行，每行 25–60 个中文字：
研究什么：用自然、易懂但专业的中文说明标题明确指向的研究对象、问题或关系。
为什么值得关注：只根据标题可以合理判断的学术背景说明这个问题为什么值得关注；如果连这一点也无法可靠判断，就写“仅凭标题无法进一步判断”。

要求：
- 不得猜测具体数据、方法、模型、机制、定量结果或结论。
- 不要逐词翻译英文标题，不要堆砌术语。
- 不要写任何额外说明、序号、Markdown 或开场白。"""

    return f"""论文标题：{title}
期刊：{journal}
摘要来源：{source_name}
英文摘要：
{source_text}

请把这篇论文整理成“科研人员真正想快速知道的 4 个问题”。目标不是翻译摘要，而是帮助地球科学、水文学、遥感、气候与洪水研究相关的研究人员或研究生，在几十秒内判断这篇文章的新意、最有意思的发现和阅读价值。

请严格输出下面 4 行，每行约 30–80 个中文字：
新在哪里：说明相对于已有认知、常见做法或过去研究，这篇文章真正新增了什么。创新可以是新的科学认识、现象、尺度、数据、方法、机制联系或验证；优先讲“科学上新知道了什么”，不要把“用了某模型”本身当成创新。如果摘要没有明确支持相对既有工作的创新点，就写“摘要未明确说明相对既有工作的创新点”。
有意思的现象：挑出摘要里最反常、最有辨识度、最值得记住的结果，例如南北半球不对称、阈值、反转、空间差异、时间变化、模型与观测不一致、极端事件中的特殊响应等。如果没有明显反常现象，就用容易理解的话概括最核心的发现。
怎么解释：说明作者如何解释这个现象，或用什么关键证据/分析把现象与机制联系起来。必须区分“观察到相关关系”和“证明了机制或因果”。如果摘要没有给出机制解释，就明确写“摘要主要报告现象，未给出明确的机制解释”。
为什么重要：说明这个发现具体改变了我们对什么过程的理解，或会怎样影响模型、预测、监测、风险评估或决策。不要只写“具有重要意义”；必须说清楚重要在哪里。只有摘要明确支持时才能写政策或应用价值。

整体写作要求：
- 专业但容易看懂，像一个懂这个领域的研究者向相邻方向同行解释论文。
- 术语必须准确，但不为显得专业而堆术语；必要术语第一次出现时可用几个字顺手解释。
- 优先保留最帮助理解结论的 1–2 个数字、时间范围或空间范围，不要罗列所有数字。
- 多用短句和明确逻辑，避免“基于……通过……构建……实现……”式摘要腔。
- 不逐句翻译，不添加摘要没有的信息，不夸大结论，不把相关性写成因果。
- 四个点之间尽量不要重复同一句信息。
- 不要输出任何额外说明、序号、Markdown 或开场白。"""


def generate_summary_zh(paper, source_text, source_name, api_key, base_url, model):
    title = normalize_space(paper.get("title"))
    journal = normalize_space(paper.get("journal"))
    user_prompt = build_summary_prompt(title, journal, source_text, source_name)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一名地球科学与水文学领域的资深研究者兼学术编辑。你的任务不是复述论文摘要，而是提炼一篇论文最值得研究者关注的信息。"
                    "你特别擅长判断：文章到底新在哪里、最有意思或反常的现象是什么、作者提供了怎样的机制解释或证据、以及这项发现具体为什么重要。"
                    "你的中文要科学准确、专业但不晦涩。优先讲科学问题和新认识，而不是技术名词；用自然中文解释复杂概念。"
                    "严格区分现象、相关性、机制和因果。凡是摘要没有提供的证据，不得自行补充或推断。"
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 620,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    url = chat_completions_url(base_url)

    last_error = None
    for attempt in range(1, LLM_MAX_ATTEMPTS + 1):
        timeout = LLM_TIMEOUT if attempt == 1 else LLM_RETRY_TIMEOUT
        try:
            response = request_chat_once(url, headers, payload, timeout)
            summary = extract_llm_content(response.json())
            return validate_guide(summary, source_name)
        except NonRetryableLLMError:
            raise
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError, ValueError, RuntimeError) as exc:
            last_error = exc
            if attempt >= LLM_MAX_ATTEMPTS:
                break
            backoff = min(2 * attempt, LLM_BACKOFF_CAP_SECONDS)
            print(
                f"LLM guide attempt {attempt}/{LLM_MAX_ATTEMPTS} failed; "
                f"retrying after {backoff}s: {exc}"
            )
            time.sleep(backoff)

    raise RuntimeError(
        f"LLM guide failed after {LLM_MAX_ATTEMPTS} attempts: {last_error}"
    )


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

    print(
        f"Generating or refreshing Chinese guides for {len(candidates)} Paper Radar entries "
        f"with prompt v{SUMMARY_PROMPT_VERSION}; up to {LLM_MAX_ATTEMPTS} attempts per paper."
    )
    changed = 0
    failed = 0
    source_counts = {}
    failed_labels = []

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
            print(f"[{index}/{len(candidates)}] guide generated ({source_name}): {label}")
        except Exception as exc:
            failed += 1
            failed_labels.append(label)
            print(
                f"::warning::[{index}/{len(candidates)}] Chinese guide failed after "
                f"up to {LLM_MAX_ATTEMPTS} attempts for {label}: {exc}"
            )
            print("::warning::Continuing with the remaining historical Paper Radar entries.")
        if index < len(candidates):
            time.sleep(LLM_PACING_SECONDS)

    if changed:
        payload["summaryPipeline"] = {
            "lastGeneratedAt": utc_now_iso(),
            "generatedThisRun": changed,
            "failedThisRun": failed,
            "sourceCounts": source_counts,
            "mode": "question-led-four-point-guide",
            "promptVersion": SUMMARY_PROMPT_VERSION,
            "maxAttemptsPerPaper": LLM_MAX_ATTEMPTS,
            "failurePolicy": "continue-through-batch",
        }
        OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            f"Saved {changed} Chinese guides with prompt v{SUMMARY_PROMPT_VERSION}; "
            f"{failed} failed and remain eligible for a later recovery run."
        )
    else:
        print(
            f"No Chinese guides were saved; all {failed} attempted entries failed, "
            "but the batch was processed without an early-stop circuit breaker."
        )

    if failed_labels:
        print("Failed entries this run:")
        for label in failed_labels:
            print(f"- {label}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
