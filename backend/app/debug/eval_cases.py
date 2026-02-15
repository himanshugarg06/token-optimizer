#!/usr/bin/env python3
"""
Local evaluation harness: run a suite of varied /v1/optimize cases and summarize
where the optimizer is currently weak (no/negative savings, fallback, etc.).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx


@dataclass(frozen=True)
class Case:
    name: str
    payload: Dict[str, Any]
    expect: Optional[str] = None  # free-form expectation note


def _mk_big_text(prefix: str, n: int) -> str:
    return (prefix + " ") * n


def _tool_schema(verbose: bool = True) -> Dict[str, Any]:
    if not verbose:
        return {"name": "getWeather", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}
    return {
        "name": "getWeather",
        "description": "Get the weather for a city. This description is intentionally verbose. " + ("More details. " * 100),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name. " + ("extra " * 50)},
                "unit": {"type": "string", "enum": ["c", "f"], "description": "Temperature unit. " + ("extra " * 50)},
            },
            "required": ["city"],
        },
        "examples": [{"city": "San Francisco", "unit": "f"}],
    }


def _rag_docs(kind: str) -> List[Dict[str, Any]]:
    if kind == "content_metadata":
        return [
            {"content": "Very long irrelevant doc. " + ("blah " * 2000), "metadata": {"source": "doc_1", "type": "doc"}},
            {"content": "Short relevant doc: The answer is 4.", "metadata": {"source": "doc_2", "type": "doc"}},
        ]
    if kind == "legacy_text":
        return [
            {"text": "Legacy RAG format doc. " + ("x " * 1500), "id": "legacy-1", "source": "legacy"},
        ]
    if kind == "empty":
        return [{"content": "  ", "metadata": {"source": "empty"}}]
    raise ValueError(kind)


def build_cases() -> List[Case]:
    model = os.getenv("EVAL_MODEL", "gpt-4o-mini")
    base_max = int(os.getenv("EVAL_MAX_INPUT_TOKENS", "300"))

    cases: List[Case] = []

    cases.append(Case(
        name="01_minimal_noop",
        payload={"model": model, "max_tokens": 8000, "messages": [{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "Hi"}]},
        expect="No optimization expected",
    ))

    cases.append(Case(
        name="02_dedup_user",
        payload={"model": model, "max_tokens": 8000, "messages": [{"role": "user", "content": "Hello"}, {"role": "user", "content": "Hello"}, {"role": "user", "content": "Hello"}]},
        expect="Should deduplicate repeated identical blocks",
    ))

    cases.append(Case(
        name="03_junk_assistant_removed",
        payload={"model": model, "max_tokens": 8000, "messages": [
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Sure, I can help with that!"},
            {"role": "assistant", "content": "Of course!"},
            {"role": "user", "content": "Question 2"},
        ]},
        expect="Generic assistant fluff should be removed (if not must_keep)",
    ))

    cases.append(Case(
        name="04_constraints_extract_increase",
        payload={"model": model, "max_tokens": 8000, "messages": [
            {"role": "system", "content": "You MUST output JSON. NEVER include PII. ALWAYS validate input."},
            {"role": "user", "content": "Process this."},
        ]},
        expect="May increase tokens due to constraint block; correctness over savings",
    ))

    log_blob = "\n".join([f"INFO step={i} doing things" for i in range(1500)])
    cases.append(Case(
        name="05_trim_logs",
        payload={"model": model, "max_tokens": 8000, "messages": [
            {"role": "user", "content": "Here are logs"},
            {"role": "assistant", "content": log_blob},
            {"role": "user", "content": "What is the error?"},
        ]},
        expect="Should trim assistant log-like content",
    ))

    # TOON JSON array compression (doc blocks only)
    json_array = json.dumps([{"id": str(i), "name": f"name_{i}", "value": i} for i in range(500)])
    cases.append(Case(
        name="06_toon_json_array_doc",
        payload={"model": model, "max_tokens": 8000, "messages": [{"role": "user", "content": "Summarize docs"}], "rag_context": [{"content": json_array, "metadata": {"source": "json_doc", "type": "doc"}}]},
        expect="Should TOON-compress JSON array inside doc blocks",
    ))

    cases.append(Case(
        name="07_rag_shape_content_metadata",
        payload={"model": model, "max_tokens": base_max, "messages": [{"role": "user", "content": "What is 2+2?"}], "rag_context": _rag_docs("content_metadata")},
        expect="RAG docs should be ingested; semantic should select relevant doc when over budget",
    ))

    cases.append(Case(
        name="08_rag_shape_legacy_text",
        payload={"model": model, "max_tokens": base_max, "messages": [{"role": "user", "content": "Summarize"}], "rag_context": _rag_docs("legacy_text")},
        expect="Legacy RAG docs should be ingested",
    ))

    cases.append(Case(
        name="09_rag_empty_docs_skipped",
        payload={"model": model, "max_tokens": base_max, "messages": [{"role": "user", "content": "Summarize"}], "rag_context": _rag_docs("empty")},
        expect="Empty RAG docs should be skipped",
    ))

    cases.append(Case(
        name="10_overbudget_must_keep_only",
        payload={"model": model, "max_tokens": 300, "messages": [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": _mk_big_text("Must-keep because last user", 4000)},
        ]},
        expect="Expected weakness: if the oversized last user message is must_keep, semantic/compress can't help unless allow_must_keep=true",
    ))

    cases.append(Case(
        name="11_overbudget_optional_earlier_turn",
        payload={"model": model, "max_tokens": 300, "messages": [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": _mk_big_text("Earlier optional background", 4000)},
            {"role": "assistant", "content": "OK."},
            {"role": "user", "content": "IMPORTANT: reply with exactly ok."},
        ]},
        expect="Should drop earlier background via semantic selection (when keep_last_n_turns=1)",
    ))

    cases.append(Case(
        name="12_tool_schema_minimization",
        payload={"model": model, "max_tokens": base_max, "messages": [{"role": "user", "content": "Call the tool"}], "tools": _tool_schema(verbose=True)},
        expect="Expected weakness: tools are serialized with str() today, so minimize_tool_schemas may not trigger",
    ))

    cases.append(Case(
        name="13_tool_outputs_large",
        payload={"model": model, "max_tokens": base_max, "messages": [{"role": "user", "content": "Analyze tool output"}], "tool_outputs": [{"tool": "bigTool", "text": _mk_big_text("tool output", 5000)}]},
        expect="Tool outputs are optional; semantic should select or compression should shrink when over budget",
    ))

    cases.append(Case(
        name="14_many_turns_keep_last_effect",
        payload={"model": model, "max_tokens": 400, "messages": (
            [{"role": "system", "content": "You are helpful."}]
            + sum(([{"role": "user", "content": _mk_big_text(f"Q{i}", 400)}, {"role": "assistant", "content": "A."}] for i in range(5)), [])
            + [{"role": "user", "content": "Final: answer ok"}]
        )},
        expect="Should keep only last turn(s); weakness shows up if KEEP_LAST_N_TURNS too high",
    ))

    cases.append(Case(
        name="15_dedup_cross_role_not_done",
        payload={"model": model, "max_tokens": 8000, "messages": [
            {"role": "user", "content": "Same content"},
            {"role": "assistant", "content": "Same content"},
            {"role": "user", "content": "Same content"},
        ]},
        expect="Dedup is content-fingerprint based but role/type can differ; verify behavior",
    ))

    # Variants to reach >= 20
    cases.append(Case(
        name="16_no_system_present",
        payload={"model": model, "max_tokens": 8000, "messages": [{"role": "assistant", "content": "Hello"}, {"role": "assistant", "content": "World"}]},
        expect="Validation expects system or user; fallback may happen",
    ))

    cases.append(Case(
        name="17_long_doc_under_budget_no_semantic",
        payload={"model": model, "max_tokens": 8000, "messages": [{"role": "user", "content": "Use docs"}], "rag_context": [{"content": _mk_big_text("doc", 800), "metadata": {"source": "doc", "type": "doc"}}]},
        expect="Under budget: semantic shouldn't trigger; heuristics+toon only",
    ))

    cases.append(Case(
        name="18_compression_candidate_short_block",
        payload={"model": model, "max_tokens": 200, "messages": [{"role": "user", "content": _mk_big_text("short", 60)}, {"role": "user", "content": "final"}]},
        expect="Compression skips <100 tokens; might remain over budget if must_keep dominates",
    ))

    cases.append(Case(
        name="19_mixed_json_nonlist_doc",
        payload={"model": model, "max_tokens": 8000, "messages": [{"role": "user", "content": "Summarize"}], "rag_context": [{"content": json.dumps({"a": 1, "b": 2}), "metadata": {"source": "obj", "type": "doc"}}]},
        expect="TOON only handles JSON arrays; object docs won't compress",
    ))

    cases.append(Case(
        name="20_big_assistant_nonlog",
        payload={"model": model, "max_tokens": 8000, "messages": [
            {"role": "user", "content": "Here is a long essay"},
            {"role": "assistant", "content": _mk_big_text("This is prose.", 2000)},
            {"role": "user", "content": "Summarize in 1 line"},
        ]},
        expect="No log trimming; only semantic/compression if over budget and optional exists",
    ))

    return cases


def main() -> int:
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:8000")
    api_key = os.getenv("API_KEY", "dev-key-12345")
    timeout_s = float(os.getenv("EVAL_TIMEOUT_S", "120"))

    cases = build_cases()
    assert len(cases) >= 20

    client = httpx.Client(timeout=timeout_s)
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    print(f"base_url={base_url} cases={len(cases)} timeout_s={timeout_s}")
    print("name\tbefore\tafter\tsaved\troute\tfallback\tcache\tover_budget\tsemantic\tcompression\tmust_keep\toptional")

    weak: List[Dict[str, Any]] = []

    for case in cases:
        t0 = time.time()
        r = client.post(f"{base_url}/v1/optimize", headers=headers, json=case.payload)
        dt_ms = int((time.time() - t0) * 1000)
        r.raise_for_status()
        data = r.json()

        stats = data["stats"]
        debug = data.get("debug", {})
        feats = debug.get("features_used", {})

        before = int(stats["tokens_before"])
        after = int(stats["tokens_after"])
        saved = int(stats["tokens_saved"])
        route = stats.get("route", "?")
        fallback = bool(stats.get("fallback_used"))
        cache_hit = bool(stats.get("cache_hit"))

        over_budget = bool(feats.get("over_budget", False))
        semantic_trig = bool(feats.get("semantic_triggered", False))
        comp_trig = bool(feats.get("compression_triggered", False))
        must_keep = int(feats.get("must_keep_tokens", 0))
        optional = int(feats.get("optional_tokens", 0))

        print(
            f"{case.name}\t{before}\t{after}\t{saved}\t{route}\t{str(fallback).lower()}\t"
            f"{str(cache_hit).lower()}\t{str(over_budget).lower()}\t{str(semantic_trig).lower()}\t"
            f"{str(comp_trig).lower()}\t{must_keep}\t{optional}"
        )

        # Mark weak cases with concrete reasons
        reasons: List[str] = []
        if saved <= 0 and before >= 500:
            reasons.append("no_savings_on_large_input")
        if fallback:
            reasons.append("fallback_used")
        if over_budget and (not semantic_trig) and (not comp_trig) and optional > 0:
            reasons.append("over_budget_but_no_semantic_or_compress")
        if over_budget and optional == 0:
            reasons.append("over_budget_but_all_must_keep")
        if "tools" in case.payload and not feats.get("enable_tool_minimization", True):
            reasons.append("tool_minimization_disabled")

        if reasons:
            weak.append({
                "case": case.name,
                "reasons": reasons,
                "before": before,
                "after": after,
                "route": route,
                "ms": dt_ms,
                "features": {k: feats.get(k) for k in [
                    "semantic_enabled",
                    "compression_enabled",
                    "embedding_model_available",
                    "over_budget",
                    "semantic_triggered",
                    "compression_triggered",
                    "must_keep_tokens",
                    "optional_tokens",
                    "must_keep_exceeds_budget",
                ]},
                "expect": case.expect,
            })

    print("\nWEAK_CASES_JSON")
    print(json.dumps(weak, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
