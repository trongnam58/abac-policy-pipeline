# -*- coding: utf-8 -*-
"""Sinh bất biến OCL từ policy JSON theo 3 mẫu IP."""
from __future__ import annotations

from ..schema import Policy
from . import patterns


def _q(text: str) -> str:
    return text.replace("'", "’")


def generate(p: Policy) -> list[str]:
    """Sinh danh sách bất biến OCL cho một policy (mỗi hành động một bất biến)."""
    if not p.actions:
        return []
    role = p.subjects[0].role if p.subjects else "student"
    network = next((e.namespace for e in p.environments if e.namespace), None)
    condition = None
    if p.conditions:
        condition = p.conditions[0].text
    elif any(e.trigger_phrase for e in p.environments):
        condition = next(e.trigger_phrase for e in p.environments if e.trigger_phrase)
    condition = condition or "default"
    executed = "true" if p.decision == "permit" else "false"

    if p.decision == "deny" and p.resource:
        template = patterns.CONTEXTUAL_USER_RESTRICTED
        use_object = True
    elif p.resource:
        template = patterns.CONTEXTUAL_USER_OBJECT
        use_object = True
    else:
        template = patterns.CONTEXTUAL_USER
        use_object = False

    invs = []
    for i, action in enumerate(p.actions):
        name = f"policy_{p.id}_{i + 1}"
        cond_lines = _condition_lines(network, condition, role)
        if use_object:
            text = template.format(
                name=name, action=action.operation, executed=executed,
                condition_lines=cond_lines, object_label=_q(p.resource.label))
        else:
            text = template.format(
                name=name, action=action.operation, executed=executed,
                condition_lines=cond_lines)
        invs.append(text)
    return invs


def _condition_lines(network: str | None, condition: str, role: str) -> str:
    parts = []
    if network:
        parts.append(f"network=#{network}")
    parts.append(f"consideredContext='{_q(condition)}'")
    parts.append(f"User.allInstances()->forAll(u | u.roleActivated=#{role})")
    return "\n  and ".join(parts)
