# -*- coding: utf-8 -*-
"""Sinh sơ đồ PlantUML (.puml) cho từng chính sách.

W1: sơ đồ thể hiện (instance) để nhìn nhanh chủ thể – hành động – đối tượng –
ngữ cảnh. W2 sẽ dựng biểu đồ lớp đầy đủ theo siêu mô hình.
"""
from __future__ import annotations

from ..schema import Policy


def _clean(text: str, limit: int = 70) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def policy_to_puml(p: Policy) -> str:
    lines = ["@startuml", "skinparam shadowing false", "skinparam linetype ortho",
             f"' Policy {p.id}: {_clean(p.sentence)}"]
    edges = []

    subj_aliases = []
    for i, s in enumerate(p.subjects):
        alias = f"S{i + 1}"
        subj_aliases.append(alias)
        label = s.role or "subject"
        if s.membership:
            label += f" ({s.membership})"
        if s.position:
            label += f" [{s.position}]"
        lines.append(f'object "{label}" as {alias}')

    for i, a in enumerate(p.actions):
        alias = f"A{i + 1}"
        lines.append(f'object "{a.verb} → {a.operation}" as {alias}')
        for s in subj_aliases:
            edges.append(f"{s} --> {alias} : subject")

    if p.resource:
        lines.append(f'object "Object: {_clean(p.resource.label, 40)}" as O1')
        for i in range(len(p.actions)):
            edges.append(f"A{i + 1} --> O1 : object")

    for i, e in enumerate(p.environments):
        alias = f"E{i + 1}"
        if e.namespace:
            label = f"Environment: {e.namespace}"
        elif e.time_from:
            label = f"Environment: {e.time_from}–{e.time_to}"
        else:
            label = "Environment"
        lines.append(f'object "{label}" as {alias}')
        for a in range(len(p.actions)):
            edges.append(f"A{a + 1} --> {alias} : environments")

    if p.conditions:
        lines.append(f'note right: condition: {_clean(p.conditions[0].text, 60)}')

    lines.extend(edges)
    lines.append("@enduml")
    return "\n".join(lines)


def dataset_to_puml(policies: list[Policy]) -> str:
    parts = [policy_to_puml(p) for p in policies]
    return "\n\n' ====================\n\n".join(parts)
