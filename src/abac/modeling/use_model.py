# -*- coding: utf-8 -*-
"""Mô-đun 2 — tạo mô hình biểu diễn chính sách ABAC theo ngữ cảnh (CPRM).

Áp dụng các phép biến đổi ở mục 3.1 của bài báo lên siêu mô hình (metamodel.py):
  - nhãn tài nguyên (object label) -> lớp tài nguyên phi con người thay cho ObjectType;
  - SubjectType không được thay thế -> bị loại khỏi mô hình;
  - giá trị role -> enum Role; namespace -> enum Network; phòng ban -> enum ORG;
  - mỗi hành động -> thuộc tính <OP>executed của lớp Action;
  - thuộc tính otherAttributes bị loại.
Đầu ra: đặc tả USE (.use) và kịch bản thể hiện SOIL (.soil) để USE kiểm tra.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from ..ocl.patterns import expected_executed, negate, witness_number
from ..schema import Policy, PolicyDataset
from . import metamodel as mm


@dataclass
class RepresentationModel:
    enums: dict[str, list[str]]
    classes: dict[str, list[tuple[str, str]]]
    resource_classes: dict[str, str] = field(default_factory=dict)  # tên lớp -> tên vai trò
    associations: list[tuple] = field(default_factory=list)
    operations: list[str] = field(default_factory=list)

    def attribute_names(self, cls: str) -> set[str]:
        return {name for name, _ in self.classes.get(cls, [])}


# ---------------------------------------------------------------------------
# Biến đổi siêu mô hình -> mô hình biểu diễn
# ---------------------------------------------------------------------------

# từ khoá của USE/OCL không được dùng làm tên
RESERVED = {
    "abstract", "aggregation", "and", "association", "associationclass", "attributes",
    "begin", "between", "class", "composition", "constraints", "context", "declare", "do",
    "else", "end", "endif", "enum", "false", "for", "if", "implies", "in", "inv", "let",
    "model", "not", "null", "operations", "or", "ordered", "post", "pre", "role", "self",
    "then", "true", "xor", "result",
}


def ident(value: str) -> str:
    """Giá trị trích xuất -> định danh ASCII hợp lệ cho USE (enum literal, tên thuộc tính)."""
    value = unicodedata.normalize("NFKD", value.replace("đ", "d").replace("Đ", "D"))
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"\W+", "_", value.strip()).strip("_")
    if not value or value[0].isdigit() or value.lower() in RESERVED:
        return f"v_{value}"
    return value


def build_model(dataset: PolicyDataset) -> RepresentationModel:
    policies = dataset.policies
    enums = {name: list(values) for name, values in mm.ENUMS.items()}
    _override(enums, "Role", (s.role for p in policies for s in p.subjects if s.role))
    _override(enums, "Network", (e.namespace for p in policies for e in p.environments if e.namespace))
    _override(enums, "ORG", (s.position for p in policies for s in p.subjects
                             if s.position and s.position.endswith("_office")))
    operations = _unique(a.operation for p in policies for a in p.actions if a.operation)
    resources = _resource_attributes(policies)

    classes: dict[str, list[tuple[str, str]]] = {}
    for cls in mm.CLASSES + [mm.ASSOCIATION_CLASS]:
        if cls in ("SubjectType", "ObjectType") and (cls == "SubjectType" or resources):
            continue
        attrs = [a for a in mm.ATTRIBUTES[cls] if a[0] != "otherAttributes"]
        if cls == "Action":
            attrs += [(f"{op}executed", "Boolean") for op in operations]
        classes[cls] = attrs
    resource_classes = {}
    for entity, keys in resources.items():
        name = mm.class_name(entity)
        resource_classes[name] = mm.role_name(entity)
        classes[name] = [("id", "String")] + [(k, "String") for k in keys]
    return RepresentationModel(enums=enums, classes=classes, resource_classes=resource_classes,
                               associations=_associations(resource_classes), operations=operations)


def _override(enums: dict[str, list[str]], name: str, values) -> None:
    extracted = _unique(ident(v) for v in values)
    if extracted:
        enums[name] = extracted


def _unique(values) -> list[str]:
    return list(dict.fromkeys(values))


def _resource_attributes(policies: list[Policy]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for p in policies:
        if p.resource:
            keys = out.setdefault(ident(p.resource.entity_type), [])
            for k in map(attribute_ident, p.resource.attributes):
                if k not in keys:
                    keys.append(k)
    return out


def attribute_ident(key: str) -> str:
    """Tên thuộc tính tài nguyên; tránh trùng thuộc tính 'id' có sẵn."""
    name = ident(key)
    return f"attr_{name}" if name == "id" else name


def _associations(resource_classes: dict[str, str]) -> list[tuple]:
    out = []
    for kind, name, end1, end2 in mm.ASSOCIATIONS:
        if "SubjectType" in (end1[0], end2[0]):
            continue
        if "ObjectType" in (end1[0], end2[0]) and resource_classes:
            continue
        out.append((kind, name, end1, end2))
    for cls, role in resource_classes.items():
        out.append(("association", f"Object_{cls}", ("Object", "1", "object"), (cls, "*", role)))
    return out


# ---------------------------------------------------------------------------
# Xuất đặc tả USE
# ---------------------------------------------------------------------------

HEADER = """-- Mô hình biểu diễn chính sách ABAC theo ngữ cảnh (sinh tự động, mô-đun 2)
-- Nguồn: src/abac/modeling/use_model.py — kiểm tra bằng: use -c policies.use
"""


def model_to_use(model: RepresentationModel, invariants: list[str], name: str = "ABACPolicies") -> str:
    parts = [HEADER, f"model {name}", "-- ===== Kiểu liệt kê ====="]
    parts += [f"enum {n} {{ {', '.join(v)} }}" for n, v in model.enums.items()]
    parts.append("-- ===== Lớp =====")
    parts += [_class_block("class", cls, attrs) for cls, attrs in model.classes.items()
              if cls != mm.ASSOCIATION_CLASS]
    parts.append("-- ===== Liên kết =====")
    parts += [_association_block(*a) for a in model.associations]
    parts.append(_association_class_block(model.classes[mm.ASSOCIATION_CLASS]))
    if invariants:
        parts.append("-- ===== Bất biến OCL (mô-đun 3) =====\nconstraints")
        parts += invariants
    return "\n\n".join(parts) + "\n"


def _class_block(keyword: str, cls: str, attrs: list[tuple[str, str]]) -> str:
    lines = [f"{keyword} {cls}"]
    if attrs:
        lines.append("attributes")
        lines += [f"  {n} : {t}" for n, t in attrs]
    lines.append("end")
    return "\n".join(lines)


def _association_block(kind: str, name: str, end1: tuple, end2: tuple) -> str:
    ends = "\n".join(f"  {c}[{m}] role {r}" for c, m, r in (end1, end2))
    return f"{kind} {name} between\n{ends}\nend"


def _association_class_block(attrs: list[tuple[str, str]]) -> str:
    ends = "\n".join(f"  {c}[{m}] role {r}" for c, m, r in mm.CONTEXT_ENDS)
    body = "\n".join(f"  {n} : {t}" for n, t in attrs)
    return f"associationclass {mm.ASSOCIATION_CLASS} between\n{ends}\nattributes\n{body}\nend"


def dataset_to_use(dataset: PolicyDataset, invariants: list[str]) -> str:
    """Giữ API cũ: dựng mô hình rồi xuất đặc tả USE."""
    return model_to_use(build_model(dataset), invariants)


# ---------------------------------------------------------------------------
# Xuất kịch bản thể hiện SOIL (trạng thái hệ thống để USE "check")
# ---------------------------------------------------------------------------

def _q(text: str) -> str:
    return text.replace("'", "’")


def dataset_to_soil(dataset: PolicyDataset, model: RepresentationModel | None = None) -> str:
    model = model or build_model(dataset)
    lines = ["-- Thể hiện của mô hình biểu diễn (sinh tự động); nạp sau policies.use"]
    for p in dataset.policies:
        lines += policy_to_soil(p, model)
    lines.append("check")
    return "\n".join(lines) + "\n"


def policy_to_soil(p: Policy, model: RepresentationModel, violate: bool = False) -> list[str]:
    """Thể hiện "chứng cứ" của policy: vế trái của bất biến đúng; violate=True đảo
    <OP>executed để bất biến phải FAILED (kiểm thử ngữ nghĩa bằng USE)."""
    st = f"nlps{p.id}"
    out = [f"-- Policy {p.id}", f"!create {st} : {mm.NLPS}",
           f"!set {st}.idSentence := '{p.id}'",
           f"!set {st}.numberExtractedAttributes := {_count_components(p)}",
           f"!set {st}.contextualSentence := {str(bool(p.conditions or p.environments)).lower()}"]
    subjects = _soil_subjects(p, st, out)
    actions = _soil_actions(p, st, out, subjects, violate)
    _soil_resource(p, st, out, actions, model)
    _soil_contexts(p, st, out, actions)
    return out


def _count_components(p: Policy) -> int:
    return (len(p.subjects) + len(p.actions) + (1 if p.resource else 0)
            + len(p.environments) + len(p.conditions))


def _soil_subjects(p: Policy, st: str, out: list[str]) -> list[str]:
    names = []
    for i, s in enumerate(p.subjects or [None], 1):
        sub, usr = f"s{p.id}_{i}", f"u{p.id}_{i}"
        out += [f"!create {sub} : Subject", f"!set {sub}.isUser := true",
                f"!create {usr} : User", f"!set {usr}.id := '{usr}'",
                f"!insert ({sub}, {usr}) into Subject_User",
                f"!insert ({st}, {sub}) into Statement_Subject"]
        if s is not None:
            out.append(f"!set {sub}.typeSubjectActivated := '{s.entity_type}'")
            if s.role:
                out.append(f"!set {usr}.roleActivated := #{ident(s.role)}")
            if s.membership:
                out.append(f"!set {usr}.typeMembership := '{_q(s.membership)}'")
            if s.position:
                out.append(f"!set {usr}.position := '{_q(s.position)}'")
        names.append(sub)
    return names


def _soil_actions(p: Policy, st: str, out: list[str], subjects: list[str],
                  violate: bool = False) -> list[str]:
    names = []
    executed = expected_executed(p)
    if violate:
        executed = "false" if executed == "true" else "true"
    operations = list(dict.fromkeys(a.operation for a in p.actions))
    for j, a in enumerate(p.actions, 1):
        act = f"a{p.id}_{j}"
        out += [f"!create {act} : Action", f"!set {act}.namesAction := '{a.operation}'",
                f"!set {act}.actionsExecuted := {executed}",
                f"!insert ({st}, {act}) into Statement_Action"]
        out += [f"!set {act}.{op}executed := {executed}" for op in operations]
        out += [f"!insert ({sub}, {act}) into Subject_Action" for sub in subjects]
        names.append(act)
    return names


def _soil_resource(p: Policy, st: str, out: list[str], actions: list[str],
                   model: RepresentationModel) -> None:
    if not p.resource:
        return
    obj, res = f"o{p.id}", f"r{p.id}"
    cls = mm.class_name(ident(p.resource.entity_type))
    out += [f"!create {obj} : Object", f"!set {obj}.isNonHumanResource := true",
            f"!set {obj}.typeObjectActivated := '{_q(p.resource.label)}'",
            f"!insert ({st}, {obj}) into Statement_Object"]
    out += [f"!insert ({act}, {obj}) into Action_Object" for act in actions]
    if cls not in model.resource_classes:
        return
    for k in range(1, _resource_instances(p) + 1):
        inst = res if k == 1 else f"{res}_{k}"
        out += [f"!create {inst} : {cls}", f"!set {inst}.id := '{inst}'",
                f"!insert ({obj}, {inst}) into Object_{cls}"]
        out += [f"!set {inst}.{attribute_ident(a)} := '{_q(v)}'" for a, v in p.resource.attributes.items()]


def _resource_instances(p: Policy) -> int:
    """Số thể hiện tài nguyên: với ràng buộc đếm, dựng đúng số vi phạm giới hạn."""
    r = p.resource
    if r is None or r.count is None or r.count_operator is None:
        return 1
    return max(int(witness_number(negate(r.count_operator), r.count)), 0)


def _soil_contexts(p: Policy, st: str, out: list[str], actions: list[str]) -> None:
    networks = [e for e in p.environments if e.namespace] or [None]
    timed = [e for e in p.environments if e.env_type in ("temporal", "duration")]
    considered = context_label(p)
    for k, net in enumerate(networks, 1):
        env = f"e{p.id}_{k}"
        out += [f"!create {env} : Environment", f"!set {env}.id := '{env}'",
                f"!insert ({st}, {env}) into Statement_Environment"]
        for j, act in enumerate(actions, 1):
            ctx = f"c{p.id}_{j}_{k}"
            out.append(f"!create {ctx} : {mm.ASSOCIATION_CLASS} between ({act}, {env})")
            if net is not None:
                out.append(f"!set {ctx}.network := #{ident(net.namespace)}")
            if considered:
                out.append(f"!set {ctx}.consideredContext := '{_q(considered)}'")
            out += _soil_timed(ctx, timed)


def _soil_timed(ctx: str, timed: list) -> list[str]:
    out = []
    for e in timed:
        out.append(f"!set {ctx}.typeConstraintActivated := #TemporalConstraint")
        if e.time_from:
            out.append(f"!set {ctx}.timeInPoint := '{e.time_from}'")
        if e.value is not None:
            value = witness_number(e.operator or "=", e.value)
            out += [f"!set {ctx}.duration := {value}", f"!set {ctx}.durationUnit := #{e.unit}"]
    return out


def context_label(p: Policy) -> str:
    """Giá trị consideredContext: các điều kiện đã chuẩn hoá (+ chu kỳ thời lượng)."""
    labels = [c.normalized or c.text for c in p.conditions if (c.normalized or c.text)]
    for e in p.environments:
        if e.period and e.env_type == "duration":
            labels.append(f"per_{e.period}")
        elif e.period and e.env_type == "temporal" and not any(
                f"within_the_{e.period}" in label for label in labels):
            labels.append(f"within_the_{e.period}")
    return "_and_".join(labels)


def semantic_check_soil(p: Policy, model: RepresentationModel) -> str:
    """Kịch bản USE cho một policy: trạng thái tuân thủ -> check (mong đợi 0 failures),
    reset, trạng thái vi phạm -> check (mong đợi mọi bất biến của policy FAILED)."""
    lines = [f"-- Kiểm thử ngữ nghĩa policy {p.id}: trạng thái tuân thủ"]
    lines += policy_to_soil(p, model) + ["check", "reset",
                                          f"-- policy {p.id}: trạng thái vi phạm"]
    lines += policy_to_soil(p, model, violate=True) + ["check"]
    return "\n".join(lines) + "\n"
