# -*- coding: utf-8 -*-
"""Đo P/R/F1 theo thành phần: subject role, action operation, resource label,
environment namespace. Dùng gold JSON cùng schema (PolicyDataset).

W1: khung tính toán; W3 mới chạy trên gold 200 câu và xuất bảng trong báo cáo.
"""
from __future__ import annotations

from ..schema import Policy, PolicyDataset


def _prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def _component_sets(p: Policy) -> dict[str, set[str]]:
    return {
        "subject_role": {s.role for s in p.subjects if s.role},
        "action": {a.operation for a in p.actions if a.operation},
        "resource": {p.resource.entity_type} if p.resource else set(),
        "environment": {e.namespace for e in p.environments if e.namespace},
    }


def evaluate(predicted: PolicyDataset, gold: PolicyDataset) -> dict:
    components = ["subject_role", "action", "resource", "environment"]
    stats = {c: {"tp": 0, "fp": 0, "fn": 0} for c in components}
    pairs = zip(predicted.policies, gold.policies)
    n = 0
    for pred, ref in pairs:
        n += 1
        ps, gs = _component_sets(pred), _component_sets(ref)
        for c in components:
            stats[c]["tp"] += len(ps[c] & gs[c])
            stats[c]["fp"] += len(ps[c] - gs[c])
            stats[c]["fn"] += len(gs[c] - ps[c])
    out = {"policies": n}
    for c in components:
        out[c] = _prf(**stats[c])
    micro = {k: sum(stats[c][k] for c in components) for k in ("tp", "fp", "fn")}
    out["micro"] = _prf(**micro)
    return out
