# -*- coding: utf-8 -*-
"""Schema trung gian (JSON) cho chính sách ABAC theo ngữ cảnh.

Dùng dataclass thuần để skeleton chạy không cần thư viện ngoài.
Khi nhóm cài Pydantic (xem requirements.txt) có thể thay lớp này bằng
model Pydantic mà giữ nguyên tên trường, phục vụ validate chặt hơn.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Subject:
    role: str = ""
    entity_type: str = "user"
    membership: Optional[str] = None
    position: Optional[str] = None


@dataclass
class Action:
    verb: str = ""
    operation: str = ""


@dataclass
class Resource:
    label: str = ""
    entity_type: str = "resource"
    # cặp thuộc tính–giá trị của lớp tài nguyên (vd. {"level": "department"})
    attributes: dict[str, str] = field(default_factory=dict)
    # ràng buộc đếm, vd. "at most one graduation project topic" -> ("<=", 1)
    count_operator: Optional[str] = None
    count: Optional[int] = None


@dataclass
class Environment:
    id: str = "env"
    env_type: str = "network"          # network | temporal | duration | location | device
    namespace: Optional[str] = None
    trigger_phrase: Optional[str] = None
    time_from: Optional[str] = None
    time_to: Optional[str] = None
    raw: Optional[str] = None
    # ràng buộc thời lượng, vd. "more than 560 hours per year"
    operator: Optional[str] = None     # < | <= | = | <> | > | >=
    value: Optional[float] = None
    unit: Optional[str] = None         # giá trị enum TimeUnit
    period: Optional[str] = None       # year | month | week | day


@dataclass
class Condition:
    text: str = ""
    kind: str = "condition"            # condition | restriction | approval | precondition | scope | subject_scope
    normalized: Optional[str] = None   # dạng chuẩn hoá dùng cho consideredContext


@dataclass
class Policy:
    id: int = 0
    sentence: str = ""
    decision: str = "permit"           # permit | deny
    modality: str = "can"
    subjects: list[Subject] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    resource: Optional[Resource] = None
    environments: list[Environment] = field(default_factory=list)
    conditions: list[Condition] = field(default_factory=list)
    logical_operator: str = "and"      # and | or — nối các giá trị thay thế cùng thuộc tính

    def to_dict(self) -> dict:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Policy":
        return _policy_from_dict(d)


@dataclass
class PolicyDataset:
    domain: str = "education"
    source: str = "vact"
    policies: list[Policy] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "source": self.source,
            "policies": [p.to_dict() for p in self.policies],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PolicyDataset":
        return cls(
            domain=d.get("domain", "education"),
            source=d.get("source", "vact"),
            policies=[Policy.from_dict(x) for x in d.get("policies", [])],
        )


def _to_dict(obj):
    if hasattr(obj, "__dataclass_fields__"):
        return {name: _to_dict(getattr(obj, name)) for name in obj.__dataclass_fields__}
    if isinstance(obj, list):
        return [_to_dict(x) for x in obj]
    return obj


OCL_OPERATORS = ("<", "<=", "=", "<>", ">", ">=")
TIME_UNITS = ("seconds", "minutes", "hours", "days", "months", "years", "am", "pm")


def _environment_from_dict(e: dict) -> Environment:
    """Dựng Environment và loại giá trị không hợp lệ (vd. JSON do LLM sinh)."""
    env = Environment(**{k: e.get(k) for k in (
        "id", "env_type", "namespace", "trigger_phrase", "time_from", "time_to", "raw",
        "operator", "value", "unit", "period")})
    env.id = env.id or "env"
    env.env_type = env.env_type or "network"
    try:
        env.value = float(env.value) if env.value is not None else None
    except (TypeError, ValueError):
        env.value = None
    if env.operator not in OCL_OPERATORS:
        env.operator = None
    if env.unit not in TIME_UNITS:
        env.unit = None
    if env.value is None or env.unit is None:
        env.value, env.unit, env.operator = None, None, None
    return env


def _resource_from_dict(r: dict) -> Resource:
    res = Resource(label=r.get("label") or "", entity_type=r.get("entity_type") or "resource",
                   attributes=dict(r.get("attributes") or {}))
    try:
        count = int(r["count"]) if r.get("count") is not None else None
    except (TypeError, ValueError):
        count = None
    if count is not None and count >= 0 and r.get("count_operator") in OCL_OPERATORS:
        res.count_operator, res.count = r["count_operator"], count
    return res


def _policy_from_dict(d: dict) -> Policy:
    p = Policy(
        id=int(d.get("id", 0)),
        sentence=d.get("sentence", ""),
        decision=d.get("decision", "permit"),
        modality=d.get("modality", "can"),
        logical_operator=d.get("logical_operator") or "and",
    )
    for s in d.get("subjects", []):
        p.subjects.append(Subject(**{k: s.get(k) for k in ("role", "entity_type", "membership", "position")}))
    for a in d.get("actions", []):
        p.actions.append(Action(**{k: a.get(k) for k in ("verb", "operation")}))
    r = d.get("resource")
    if r:
        p.resource = _resource_from_dict(r)
    for e in d.get("environments") or []:
        p.environments.append(_environment_from_dict(e))
    for c in d.get("conditions", []):
        p.conditions.append(Condition(**{k: c.get(k) for k in ("text", "kind", "normalized")}))
    return p


def save_dataset(dataset: PolicyDataset, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dataset.to_dict(), f, ensure_ascii=False, indent=2)


def load_dataset(path: str) -> PolicyDataset:
    with open(path, encoding="utf-8") as f:
        return PolicyDataset.from_dict(json.load(f))
