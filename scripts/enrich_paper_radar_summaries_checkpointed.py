#!/usr/bin/env python3
"""Run Paper Radar Chinese-guide enrichment with visible progress and checkpoints.

This wrapper reuses the source-retrieval and guide-validation logic from
``enrich_paper_radar_summaries.py`` while making three operational changes:

1. Disable LLM thinking/reasoning mode for structured guide generation.
2. Flush a progress line immediately for every paper.
3. Save ``paper-radar.json`` checkpoints periodically so completed work is not
   held only in memory until the full historical batch finishes.
"""

import json
import os
import time

import requests

import enrich_paper_radar_summaries as base

DEFAULT_CHECKPOINT_EVERY = 5


def generate_summary_non_thinking(paper, source_text, source_name, api_key, base_url, model):
    title = base.normalize_space(paper.get("title"))
    journal = base.normalize_space(paper.get("journal"))
    user_prompt = base.build_summary_prompt(title, journal, source_text, source_name)

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
        "thinking": {"type": "disabled"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    url = base.chat_completions_url(base_url)

    last_error = None
    for attempt in range(1, base.LLM_MAX_ATTEMPTS + 1):
        timeout = base.LLM_TIMEOUT if attempt == 1 else base.LLM_RETRY_TIMEOUT
        try:
            response = base.request_chat_once(url, headers, payload, timeout)
            summary = base.extract_llm_content(response.json())
            return base.validate_guide(summary, source_name)
        except base.NonRetryableLLMError:
            raise
        except (
            requests.Timeout,
            requests.ConnectionError,
            requests.HTTPError,
            ValueError,
            RuntimeError,
        ) as exc:
            last_error = exc
            if attempt >= base.LLM_MAX_ATTEMPTS:
                break
            backoff = min(2 * attempt, base.LLM_BACKOFF_CAP_SECONDS)
            print(
                f"    retry {attempt}/{base.LLM_MAX_ATTEMPTS} failed; "
                f"retrying after {backoff}s: {exc}",
                flush=True,
            )
            time.sleep(backoff)

    raise RuntimeError(
        f"LLM guide failed after {base.LLM_MAX_ATTEMPTS} attempts: {last_error}"
    )


def update_pipeline(payload, *, changed, failed, source_counts, processed, total, checkpoint_every, status):
    now = base.utc_now_iso()
    payload["summaryPipeline"] = {
        "lastGeneratedAt": now,
        "lastCheckpointAt": now,
        "generatedThisRun": changed,
        "failedThisRun": failed,
        "processedThisRun": processed,
        "totalCandidatesThisRun": total,
        "sourceCounts": source_counts,
        "mode": "question-led-four-point-guide-non-thinking",
        "promptVersion": base.SUMMARY_PROMPT_VERSION,
        "maxAttemptsPerPaper": base.LLM_MAX_ATTEMPTS,
        "failurePolicy": "continue-through-batch",
        "thinkingMode": "disabled",
        "checkpointEvery": checkpoint_every,
        "status": status,
    }


def save_checkpoint(payload, *, changed, failed, source_counts, processed, total, checkpoint_every, status):
    update_pipeline(
        payload,
        changed=changed,
        failed=failed,
        source_counts=source_counts,
        processed=processed,
        total=total,
        checkpoint_every=checkpoint_every,
        status=status,
    )
    base.OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"CHECKPOINT saved: {processed}/{total} processed; "
        f"{changed} generated; {failed} failed; status={status}.",
        flush=True,
    )


def main():
    api_key = base.normalize_space(os.environ.get("PAPER_RADAR_LLM_API_KEY"))
    base_url = base.normalize_space(os.environ.get("PAPER_RADAR_LLM_BASE_URL"))
    model = base.normalize_space(os.environ.get("PAPER_RADAR_LLM_MODEL"))
    if not api_key or not base_url or not model:
        print(
            "::warning::Paper Radar Chinese summaries skipped: "
            "LLM API key/base URL/model is not fully configured.",
            flush=True,
        )
        return 0

    if not base.OUTPUT.exists():
        print(
            "::warning::Paper Radar Chinese summaries skipped: paper-radar.json does not exist.",
            flush=True,
        )
        return 0

    payload = json.loads(base.OUTPUT.read_text(encoding="utf-8"))
    papers = payload.get("papers") or []
    if not isinstance(papers, list):
        raise RuntimeError("paper-radar.json papers must be a list")

    try:
        max_per_run = max(
            1,
            int(os.environ.get("PAPER_RADAR_SUMMARY_MAX_PER_RUN", base.DEFAULT_MAX_PER_RUN)),
        )
    except ValueError:
        max_per_run = base.DEFAULT_MAX_PER_RUN

    try:
        checkpoint_every = max(
            1,
            int(os.environ.get("PAPER_RADAR_CHECKPOINT_EVERY", DEFAULT_CHECKPOINT_EVERY)),
        )
    except ValueError:
        checkpoint_every = DEFAULT_CHECKPOINT_EVERY

    candidates = [
        paper
        for paper in papers
        if isinstance(paper, dict) and base.summary_needs_refresh(paper)
    ]
    candidates.sort(
        key=lambda paper: (
            paper.get("publicationDate") or "",
            paper.get("title") or "",
        ),
        reverse=True,
    )
    candidates = candidates[:max_per_run]

    if not candidates:
        print(
            f"All Paper Radar entries already use Chinese guide prompt "
            f"v{base.SUMMARY_PROMPT_VERSION}; no LLM calls needed.",
            flush=True,
        )
        return 0

    total = len(candidates)
    print(
        f"Generating or refreshing {total} Chinese guides with prompt "
        f"v{base.SUMMARY_PROMPT_VERSION}; thinking=disabled; "
        f"checkpoint every {checkpoint_every} papers; "
        f"up to {base.LLM_MAX_ATTEMPTS} attempts per paper.",
        flush=True,
    )

    changed = 0
    failed = 0
    source_counts = {}
    failed_labels = []

    for index, paper in enumerate(candidates, start=1):
        label = base.normalize_space(paper.get("doi") or paper.get("title"))[:100]
        started = time.monotonic()
        print(f"[{index}/{total}] START {label}", flush=True)

        try:
            source_text, source_name = base.get_summary_source_text(paper)
            summary = generate_summary_non_thinking(
                paper,
                source_text,
                source_name,
                api_key,
                base_url,
                model,
            )
            paper["summaryZh"] = summary
            paper["summarySource"] = source_name
            paper["summaryGeneratedAt"] = base.utc_now_iso()
            paper["summaryPromptVersion"] = base.SUMMARY_PROMPT_VERSION
            source_counts[source_name] = source_counts.get(source_name, 0) + 1
            changed += 1
            elapsed = time.monotonic() - started
            print(
                f"[{index}/{total}] DONE  generated ({source_name}) in "
                f"{elapsed:.1f}s: {label}",
                flush=True,
            )
        except Exception as exc:
            failed += 1
            failed_labels.append(label)
            elapsed = time.monotonic() - started
            print(
                f"::warning::[{index}/{total}] FAILED after {elapsed:.1f}s and "
                f"up to {base.LLM_MAX_ATTEMPTS} attempts: {label}: {exc}",
                flush=True,
            )
            print(
                "::warning::Continuing with the remaining historical Paper Radar entries.",
                flush=True,
            )

        if index % checkpoint_every == 0 or index == total:
            save_checkpoint(
                payload,
                changed=changed,
                failed=failed,
                source_counts=source_counts,
                processed=index,
                total=total,
                checkpoint_every=checkpoint_every,
                status="complete" if index == total else "in_progress",
            )

        if index < total:
            time.sleep(base.LLM_PACING_SECONDS)

    print(
        f"Finished Paper Radar guide batch: {changed}/{total} generated; "
        f"{failed} failed and remain eligible for a later recovery run.",
        flush=True,
    )

    if failed_labels:
        print("Failed entries this run:", flush=True)
        for label in failed_labels:
            print(f"- {label}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
