# -*- coding: utf-8 -*-
"""Đánh giá với gold của nhóm tác giả bài báo (policy_dataset_gold.json, repo [26]).

Gold đó dùng schema khác (và không đồng nhất: phần lớn câu dùng `subjects`/`resource`/
`environments`/`context`, một số câu dùng `subject`/`object` dạng chuỗi). Module này
quy cả gold và kết quả của pipeline về cùng các tập so sánh được:

  subject     : vai trò (head_* -> head; staff / người dùng chung -> user)
  action      : toán tử (READ, UPLOAD, ...)
  object      : danh từ chính của nhãn tài nguyên (learning_material -> material)
  environment : namespace hệ thống, "temporal", "location:<cụm>"
  condition   : cụm điều kiện ngữ cảnh (khớp mờ theo từ)

Quy tắc ánh xạ áp dụng đồng nhất cho mọi nguồn (pipeline này và output máy của tác giả).
"""
from __future__ import annotations

import re

from ..schema import Policy

FIELDS = ("subject", "action", "object", "environment", "condition")
_STOP = {"the", "a", "an", "of", "for", "in", "that", "all", "their", "its", "to", "and", "or"}


def head_noun(label: str | None) -> str:
    """'multiple-choice_exams' -> 'exam'; 'graduation_project_topics' -> 'topic'."""
    if not label:
        return ""
    tokens = [t for t in re.split(r"[\s_\-]+", label.lower()) if t]
    if not tokens:
        return ""
    word = tokens[-1]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us")):
        word = word[:-1]
    return word


def _norm_role(role: str | None) -> str:
    role = (role or "").lower().strip()
    if role.startswith("head"):
        return "head"
    if role in ("", "staff", "user", "users"):
        return "user"
    return role


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP}


# ---------------------------------------------------------------------------
# Quy đổi gold của tác giả
# ---------------------------------------------------------------------------

def _gold_env(e: dict) -> str | None:
    etype = (e.get("env_type") or "").lower()
    if etype == "temporal":
        return "temporal"
    namespaces = [s.get("namespace", "") for s in (e.get("systems") or [])]
    if e.get("namespace"):
        namespaces.append(e["namespace"])
    for ns in namespaces:
        if "device_type:" in ns:
            return ns.split(":")[-1]
    if etype == "location":
        return "location:" + "_".join(sorted(_words(e.get("trigger_phrase") or e.get("phrase") or "")))
    return None


def gold_sets(p: dict) -> dict:
    """Bản ghi gold (cả hai biến thể schema) -> các tập so sánh."""
    subjects = {_norm_role(s.get("role")) for s in p.get("subjects") or [] if isinstance(s, dict)}
    if "subjects" not in p:
        subjects |= {s.lower() for s in p.get("subject") or [] if isinstance(s, str)}
    actions = {(a.get("operation") if isinstance(a, dict) else a or "").upper()
               for a in p.get("actions") or []} - {""}
    resource = p.get("resource") if isinstance(p.get("resource"), dict) else None
    if resource:
        objects = {head_noun(resource.get("label"))}
    else:
        objects = {head_noun(o) for o in p.get("object") or [] if isinstance(o, str)}
    envs = {k for k in (_gold_env(e) for e in p.get("environments") or []) if k}
    conditions = [c.get("trigger_phrase") or "" for c in p.get("context") or [] if isinstance(c, dict)]
    return {"subject": subjects, "action": actions, "object": objects - {""},
            "environment": envs, "condition": [c for c in conditions if c]}


# ---------------------------------------------------------------------------
# Quy đổi kết quả pipeline
# ---------------------------------------------------------------------------

def policy_sets(p: Policy) -> dict:
    envs = set()
    for e in p.environments:
        if e.namespace:
            envs.add(e.namespace)
        elif e.env_type in ("temporal", "duration"):
            envs.add("temporal")
    return {
        "subject": {_norm_role(s.role) for s in p.subjects},
        "action": {a.operation for a in p.actions if a.operation},
        "object": {head_noun(p.resource.entity_type)} if p.resource else set(),
        "environment": envs,
        "condition": [c.text for c in p.conditions if c.text],
    }


# ---------------------------------------------------------------------------
# Tính điểm
# ---------------------------------------------------------------------------

def _phrases_match(a: str, b: str, threshold: float) -> bool:
    aw, bw = _words(a), _words(b)
    if not aw or not bw:
        return False
    return len(aw & bw) / len(aw | bw) >= threshold or aw <= bw or bw <= aw


def match_phrases(gold: list[str], pred: list[str], threshold: float = 0.5) -> tuple[int, int, int]:
    """Khớp tham lam: cặp khớp nếu Jaccard theo từ >= threshold hoặc một bên chứa bên kia."""
    remaining = list(pred)
    tp = 0
    for g in gold:
        for i, q in enumerate(remaining):
            if _phrases_match(g, q, threshold):
                tp += 1
                del remaining[i]
                break
    return tp, len(pred) - tp, len(gold) - tp


def _prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4),
            "tp": tp, "fp": fp, "fn": fn}


def score(pairs: list[tuple[dict, dict]]) -> dict:
    """pairs: [(gold_sets, pred_sets)] -> P/R/F1 theo trường + micro 4 trường (như tác giả) và 5 trường."""
    totals = {f: [0, 0, 0] for f in FIELDS}
    for gold, pred in pairs:
        for f in FIELDS:
            if f == "condition":
                counts = match_phrases(gold[f], pred[f])
            else:
                counts = (len(gold[f] & pred[f]), len(pred[f] - gold[f]), len(gold[f] - pred[f]))
            for i, v in enumerate(counts):
                totals[f][i] += v
    out = {f: _prf(*totals[f]) for f in FIELDS}
    out["micro_4"] = _prf(*[sum(totals[f][i] for f in FIELDS[:4]) for i in range(3)])
    out["micro_5"] = _prf(*[sum(totals[f][i] for f in FIELDS) for i in range(3)])
    return out
