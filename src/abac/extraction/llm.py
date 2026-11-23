# -*- coding: utf-8 -*-
"""Nhánh LLM (W2): gọi client, chuẩn hoá kết quả và gộp với rules.

Chế độ:
  - "off"    : chỉ rules (baseline W1)
  - "llm"    : chỉ LLM (dùng cho ablation; lỗi thì rơi về rules)
  - "hybrid" : rules + LLM bổ sung các trường rules bỏ sót (mặc định W2)
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

from ..schema import Policy
from .client import LLMClient, LLMError
from .rules import detect_language


@dataclass
class LLMConfig:
    enabled: bool = False
    mode: str = "hybrid"

    @classmethod
    def from_env(cls, mode: str = "hybrid") -> "LLMConfig":
        return cls(enabled=LLMClient.from_env() is not None, mode=mode)

    def client(self) -> "LLMClient | None":
        return LLMClient.from_env()


def safe_llm_policy(policy: Policy, client: LLMClient) -> "Policy | None":
    """Gọi LLM và dựng Policy; trả None nếu lỗi/không parse được."""
    try:
        data = dict(client.extract(policy.sentence, detect_language(policy.sentence)))
    except (LLMError, TypeError):
        return None
    data.setdefault("id", policy.id)
    data.setdefault("sentence", policy.sentence)
    data.setdefault("decision", policy.decision)
    data.setdefault("modality", policy.modality)
    data.setdefault("subjects", [])
    data.setdefault("actions", [])
    data.setdefault("resource", None)
    data.setdefault("environments", [])
    data.setdefault("conditions", [])
    try:
        return Policy.from_dict(data)
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def merge(base: Policy, extra: Policy) -> Policy:
    """rules là nền; LLM chỉ bổ sung trường trống (tránh ghi đè kết quả tốt)."""
    out = copy.deepcopy(base)
    if not out.subjects and extra.subjects:
        out.subjects = copy.deepcopy(extra.subjects)
    if not out.actions and extra.actions:
        out.actions = copy.deepcopy(extra.actions)
    if out.resource is None and extra.resource:
        out.resource = copy.deepcopy(extra.resource)
    if not out.environments and extra.environments:
        out.environments = copy.deepcopy(extra.environments)
    if not out.conditions and extra.conditions:
        out.conditions = copy.deepcopy(extra.conditions)
    # phủ định là tín hiệu an toàn: nếu rules nói permit mà LLM nói deny thì ưu tiên deny
    if base.decision == "permit" and extra.decision == "deny":
        out.decision = "deny"
        out.modality = extra.modality
    return out


def enrich_with_llm(policy: Policy, mode: str, client: "LLMClient | None") -> tuple[Policy, str]:
    """Trả (policy, trạng thái) với trạng thái: skipped | ok | fallback."""
    if client is None:
        return policy, "skipped"
    llm_policy = safe_llm_policy(policy, client)
    if llm_policy is None:
        return policy, "fallback"
    if mode == "llm":
        return llm_policy, "ok"
    return merge(policy, llm_policy), "ok"
