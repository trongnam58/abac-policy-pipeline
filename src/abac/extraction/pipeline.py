# -*- coding: utf-8 -*-
"""Điều phối trích xuất: rules (W1) + nhánh LLM (W2)."""
from __future__ import annotations

from ..schema import PolicyDataset
from . import rules
from .client import LLMClient
from .llm import enrich_with_llm

MODES = ("off", "llm", "hybrid")


def extract_with_stats(texts: list[str], domain: str = "education", source: str = "vact",
                       llm_mode: str = "off") -> tuple[PolicyDataset, dict]:
    if llm_mode not in MODES:
        raise ValueError(f"llm_mode phải thuộc {MODES}")
    client = LLMClient.from_env() if llm_mode != "off" else None
    stats = {"policies": 0, "llm_requests": 0, "llm_ok": 0, "llm_fallback": 0, "llm_skipped": 0}
    policies = []
    for text in texts:
        text = text.strip()
        if not text:
            continue
        policy = rules.build_policy(1 + len(policies), text)
        if client is not None:
            stats["llm_requests"] += 1
            policy, state = enrich_with_llm(policy, llm_mode, client)
            stats["llm_" + state] = stats.get("llm_" + state, 0) + 1
        policies.append(policy)
    stats["policies"] = len(policies)
    return PolicyDataset(domain=domain, source=source, policies=policies), stats


def extract(texts: list[str], domain: str = "education", source: str = "vact",
            use_llm: bool = False, llm_mode: str | None = None) -> PolicyDataset:
    mode = llm_mode or ("hybrid" if use_llm else "off")
    dataset, _ = extract_with_stats(texts, domain=domain, source=source, llm_mode=mode)
    return dataset
