# -*- coding: utf-8 -*-
"""Sinh khung mô hình USE (.use) từ JSON.

W1: khung lớp + kiểu liệt kê + thể hiện cho từng chính sách, kèm các bất biến
OCL sinh ở mô-đun 3. Việc hoàn thiện association/constraint để USE parse sạch
và chạy conformance test là nội dung W2–W3 (xem SOW mục 2.1, W4).
"""
from __future__ import annotations

from ..schema import Policy, PolicyDataset
from .metamodel import CLASSES, ENUMS

HEADER = """-- Mô hình ABAC theo ngữ cảnh (bản khung W1–W2, sinh tự động)
-- Nguồn: src/abac/modeling/use_model.py
-- Lưu ý: W3 hoàn thiện association và validate bằng USE trước khi dùng chính thức.

model ABACPolicies

-- ===== Lớp UML =====
"""


def _class_blocks() -> list[str]:
    attrs = {
        "User": ["id : String", "roleActivated : Role", "typeMembership : String",
                 "position : String"],
        "Subject": ["user : User", "typeSubjectActivated : String"],
        "Object": ["label : String", "isNonHumanResource : Boolean"],
        "ObjectType": ["id : String", "otherAttributes : String"],
        "Action": ["namesAction : String", "actionsExecuted : Boolean"],
        "Environment": ["id : String", "namespaces : Network"],
        "Context": ["id : String", "network : Network", "consideredContext : String"],
        "Natural_Language_Policy_Statement": ["sentence : String"],
        "Group": ["id : String", "numberMembers : Integer"],
    }
    blocks = []
    for cls in CLASSES:
        block = [f"class {cls}"]
        if attrs.get(cls):
            block.append("attributes")
            block.extend(f"  {a}" for a in attrs[cls])
        block.append("end")
        blocks.append("\n".join(block))
    return blocks


def _enum_blocks() -> list[str]:
    blocks = []
    for name, values in ENUMS.items():
        literal = ", ".join(values)
        blocks.append(f"enum {name} {{ {literal} }}")
    return blocks


def _instances(p: Policy) -> list[str]:
    lines = [f"-- Policy {p.id}"]
    lines.append(f"!create pol{p.id} : Natural_Language_Policy_Statement")
    lines.append(f"!set pol{p.id}.sentence := '{_q(p.sentence)}'")
    for i, s in enumerate(p.subjects):
        lines.append(f"!create u{p.id}_{i + 1} : User")
        lines.append(f"!set u{p.id}_{i + 1}.roleActivated := #{s.role or 'student'}")
        if s.membership:
            lines.append(f"!set u{p.id}_{i + 1}.typeMembership := '{s.membership}'")
        if s.position:
            lines.append(f"!set u{p.id}_{i + 1}.position := '{s.position}'")
    for i, a in enumerate(p.actions):
        lines.append(f"!create a{p.id}_{i + 1} : Action")
        lines.append(f"!set a{p.id}_{i + 1}.namesAction := '{a.operation}'")
    if p.resource:
        lines.append(f"!create o{p.id} : Object")
        lines.append(f"!set o{p.id}.label := '{_q(p.resource.label)}'")
    for i, e in enumerate(p.environments):
        lines.append(f"!create e{p.id}_{i + 1} : Environment")
        if e.namespace:
            lines.append(f"!set e{p.id}_{i + 1}.namespaces := #{e.namespace}")
    return lines


def _q(text: str) -> str:
    return text.replace("'", "’")


def dataset_to_use(dataset: PolicyDataset, invariants: list[str]) -> str:
    parts = [HEADER, "\n\n".join(_class_blocks()), "\n\n".join(_enum_blocks())]
    inst = []
    for p in dataset.policies:
        inst.extend(_instances(p))
    parts.append("\n-- ===== Thể hiện =====")
    parts.append("\n".join(inst))
    if invariants:
        parts.append("\n-- ===== Bất biến OCL (mô-đun 3) =====")
        parts.append("\n\n".join(invariants))
    parts.append("\n-- Hết mô hình khung W1.")
    return "\n\n".join(parts)
