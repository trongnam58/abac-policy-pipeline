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


@dataclass
class Environment:
    id: str = "env"
    env_type: str = "network"          # network | temporal | location | device
    namespace: Optional[str] = None
    trigger_phrase: Optional[str] = None
    time_from: Optional[str] = None
    time_to: Optional[str] = None
    raw: Optional[str] = None


@dataclass
class Condition:
    text: str = ""
    kind: str = "condition"            # condition | restriction | approval | precondition


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


def _policy_from_dict(d: dict) -> Policy:
    p = Policy(
        id=int(d.get("id", 0)),
        sentence=d.get("sentence", ""),
        decision=d.get("decision", "permit"),
        modality=d.get("modality", "can"),
    )
    for s in d.get("subjects", []):
        p.subjects.append(Subject(**{k: s.get(k) for k in ("role", "entity_type", "membership", "position")}))
    for a in d.get("actions", []):
        p.actions.append(Action(**{k: a.get(k) for k in ("verb", "operation")}))
    r = d.get("resource")
    if r:
        p.resource = Resource(**{k: r.get(k) for k in ("label", "entity_type")})
    for e in d.get("environments", []):
        p.environments.append(Environment(**{k: e.get(k) for k in (
            "id", "env_type", "namespace", "trigger_phrase", "time_from", "time_to", "raw")}))
    for c in d.get("conditions", []):
        p.conditions.append(Condition(**{k: c.get(k) for k in ("text", "kind")}))
    return p


def save_dataset(dataset: PolicyDataset, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dataset.to_dict(), f, ensure_ascii=False, indent=2)


def load_dataset(path: str) -> PolicyDataset:
    with open(path, encoding="utf-8") as f:
        return PolicyDataset.from_dict(json.load(f))
