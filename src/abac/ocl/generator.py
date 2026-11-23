# -*- coding: utf-8 -*-
"""Mô-đun 3 — sinh bất biến OCL từ policy theo thuật toán Fig. 3 của bài báo.

  IP   = selectIP(CIP_ABAC)                 -> select_ip
  S_OCL = getSampleOCLcomponent(IP)          -> patterns.InvariantPattern
  d    = getData(N_E, C); p = d              -> context_atoms / user_atoms / object_type_clause
  O_OCL = determineOCLoperator(S)           -> Environment.operator (common.ocl_operator)
  LO   = determineLogicalOperator(S)        -> Policy.logical_operator
  i_OCL = formOCLinvariant(S_OCL, p, O_OCL, LO) -> form_invariant
"""
from __future__ import annotations

from ..modeling.metamodel import class_name, role_name
from ..modeling.use_model import attribute_ident, context_label, ident
from ..schema import Action, Policy, Subject
from . import patterns
from .patterns import InvariantPattern, expected_executed, negate, select_ip

__all__ = ["generate", "generate_with_patterns", "select_ip"]

INDENT = "\n  and "
INNER = "\n        and "


def _q(text: str) -> str:
    return text.replace("'", "’")


def context_atoms(p: Policy) -> list[str]:
    """[att_C][x][val_C] — thuộc tính của associationclass Context."""
    atoms = []
    networks = [ident(e.namespace) for e in p.environments if e.namespace]
    if len(networks) == 1:
        atoms.append(f"network=#{networks[0]}")
    elif networks:
        atoms.append("(" + " or ".join(f"network=#{n}" for n in networks) + ")")
    timed = [e for e in p.environments if e.env_type in ("temporal", "duration")]
    if timed:
        atoms.append("typeConstraintActivated=#TemporalConstraint")
    for e in timed:
        if e.time_from and e.time_to:
            atoms += [f"timeInPoint >= '{e.time_from}'", f"timeInPoint <= '{e.time_to}'"]
        if e.value is not None:
            atoms += [f"duration {e.operator or '='} {_number(e.value)}",
                      f"durationUnit=#{e.unit}"]
    label = context_label(p)
    if label:
        atoms.append(f"consideredContext='{_q(label)}'")
    return atoms


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def subject_atoms(s: Subject) -> list[str]:
    atoms = []
    if s.role:
        atoms.append(f"u.roleActivated=#{ident(s.role)}")
    if s.membership:
        atoms.append(f"u.typeMembership='{_q(s.membership)}'")
    if s.position:
        atoms.append(f"u.position='{_q(s.position)}'")
    return atoms


def subject_groups(p: Policy, ip: InvariantPattern) -> list[list[Subject]]:
    """LO='or' -> một bất biến với các lựa chọn thay thế; LO='and' -> mỗi chủ thể một bất biến."""
    if not ip.user_attributes or not p.subjects:
        return [[]]
    if p.logical_operator == "or":
        return [p.subjects]
    return [[s] for s in p.subjects]


def user_atoms(group: list[Subject], logical_operator: str) -> list[str]:
    conjunctions = [" and ".join(subject_atoms(s)) for s in group]
    conjunctions = [c for c in conjunctions if c]
    if len(conjunctions) > 1:
        return ["(" + f" {logical_operator} ".join(f"({c})" for c in conjunctions) + ")"]
    return [atom for s in group for atom in subject_atoms(s)]


def user_clause(p: Policy, ip: InvariantPattern, group: list[Subject]) -> str | None:
    atoms = user_atoms(group, p.logical_operator) if ip.user_attributes else []
    if ip.object_navigation and p.resource:
        nav = f"u.subject.actions.objects.{role_name(ident(p.resource.entity_type))}"
        if ip is patterns.CONTEXTUAL_USER_CARDINALITY:
            atoms.append(f"{nav}->size() {negate(p.resource.count_operator)} {p.resource.count}")
        else:
            atoms.append(f"{nav}->notEmpty()")
    if not atoms:
        return None
    return "User.allInstances()->forAll(u | " + INNER.join(atoms) + ")"


def object_type_clause(p: Policy, ip: InvariantPattern) -> str | None:
    if not (ip.object_type_attributes and p.resource and p.resource.attributes):
        return None
    cls = class_name(ident(p.resource.entity_type))
    atoms = [f"ot.{attribute_ident(k)}='{_q(v)}'" for k, v in p.resource.attributes.items()]
    return f"{cls}.allInstances()->forAll(ot | " + " and ".join(atoms) + ")"


def form_invariant(name: str, antecedent: list[str], action: Action, executed: str) -> str:
    body = INDENT.join(antecedent) if antecedent else "true"
    return (f"context Context inv {name}:\n  {body}\n"
            f"  implies environments.actions->exists(namesAction='{action.operation}')\n"
            f"        and actions.{action.operation}executed={executed}")


def generate_with_patterns(p: Policy) -> list[tuple[str, str]]:
    """Trả [(id mẫu IP, bất biến)] cho một policy (mỗi chủ thể × hành động một bất biến)."""
    if not p.actions:
        return []
    ip = select_ip(p)
    executed = expected_executed(p)
    ctx = context_atoms(p)
    ot = object_type_clause(p, ip)
    out: list[tuple[str, str]] = []
    for group in subject_groups(p, ip):
        antecedent = ctx + [c for c in (user_clause(p, ip, group), ot) if c]
        for action in p.actions:
            name = f"policy_{p.id}_{len(out) + 1}"
            out.append((ip.id, form_invariant(name, antecedent, action, executed)))
    return out


def generate(p: Policy) -> list[str]:
    """Sinh danh sách bất biến OCL cho một policy."""
    return [inv for _, inv in generate_with_patterns(p)]
