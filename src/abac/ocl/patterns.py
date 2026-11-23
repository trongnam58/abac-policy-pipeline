# -*- coding: utf-8 -*-
"""Ba mẫu bất biến OCL (IP) hướng ABAC theo ngữ cảnh — Fig. 5, 6, 7 của bài báo.

Mỗi mẫu mô tả bằng 6 thành phần (ID, Intent, Structure, Participants, Sample OCL,
Applicability). Sample OCL chứa placeholder dạng [ký hiệu]; generator.py thay các
placeholder bằng dữ liệu trích xuất (thuật toán Fig. 3).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..schema import Policy


@dataclass(frozen=True)
class InvariantPattern:
    id: str
    intent: str
    sample_ocl: str
    user_attributes: bool          # có [att_U][x][val_U] trong forAll(u | ...)
    object_navigation: bool        # có u.subject.actions.objects.[object_type]->notEmpty()
    object_type_attributes: bool   # có [ObjectType].allInstances()->forAll(ot | ...)
    fixed_executed: str | None     # "false" với mẫu cấm; None = theo quyết định permit/deny


CONTEXTUAL_USER = InvariantPattern(
    id="ContextualUser",
    intent="Kiểm tra quyền thực thi một hành động dựa trên thuộc tính của "
           "associationclass Context và lớp User.",
    sample_ocl="""context Context inv:
  ([att1C][x][val1C] and/or ... and/or [att_nC][x][val_nC])
  and User.allInstances()->forAll(u | u.[att1U][x][val1U] and/or ...
        and/or u.[att_mU][x][val_mU]
        and u.subject.actions.objects.[object_type]->notEmpty())
  implies environments.actions->exists(namesAction='[ACTION]')
        and actions.[ACTION]executed=true/false""",
    user_attributes=True, object_navigation=True, object_type_attributes=False,
    fixed_executed=None,
)

CONTEXTUAL_USER_OBJECT_TYPE = InvariantPattern(
    id="ContextualUserObjectType",
    intent="Kiểm tra quyền thực thi một hành động dựa trên thuộc tính của Context, "
           "User và ObjectType (lớp tài nguyên phi con người).",
    sample_ocl="""context Context inv:
  ([att1C][x][val1C] and/or ... and/or [att_nC][x][val_nC])
  and User.allInstances()->forAll(u | u.[att1U][x][val1U] and/or ...
        and/or u.[att_mU][x][val_mU])
  and [ObjectType].allInstances()->forAll(ot | ot.[att1OT][x][val1OT]
        and/or ... and/or ot.[att_kOT][x][val_kOT])
  implies environments.actions->exists(namesAction='[ACTION]')
        and actions.[ACTION]executed=true/false""",
    user_attributes=True, object_navigation=False, object_type_attributes=True,
    fixed_executed=None,
)

CONTEXTUAL_USER_RESTRICTED = InvariantPattern(
    id="ContextualUserRestricted",
    intent="Cấm mọi người dùng thực thi một hành động trên ObjectType trong các "
           "điều kiện dựa trên thuộc tính của Context.",
    sample_ocl="""context Context inv:
  ([att1C][x][val1C] and/or ... and/or [att_nC][x][val_nC])
  and User.allInstances()->forAll(u |
        u.subject.actions.objects.[object_type]->notEmpty())
  implies environments.actions->exists(namesAction='[ACTION]')
        and actions.[ACTION]executed=false""",
    user_attributes=False, object_navigation=True, object_type_attributes=False,
    fixed_executed="false",
)

# Mẫu mở rộng (không có trong bài báo — mục 6 của bài báo nêu cần bổ sung IP): giới hạn
# số tài nguyên một người dùng được thao tác, vd. "register for at most one topic".
CONTEXTUAL_USER_CARDINALITY = InvariantPattern(
    id="ContextualUserCardinality",
    intent="(Mở rộng) Cấm thực thi một hành động khi số tài nguyên ObjectType gắn với "
           "người dùng vi phạm giới hạn đếm trong câu chính sách.",
    sample_ocl="""context Context inv:
  ([att1C][x][val1C] and/or ... and/or [att_nC][x][val_nC])
  and User.allInstances()->forAll(u | u.[att1U][x][val1U] and/or ...
        and u.subject.actions.objects.[object_type]->size() [not x] [n])
  implies environments.actions->exists(namesAction='[ACTION]')
        and actions.[ACTION]executed=false""",
    user_attributes=True, object_navigation=True, object_type_attributes=False,
    fixed_executed="false",
)

PATTERNS = {p.id: p for p in (CONTEXTUAL_USER, CONTEXTUAL_USER_OBJECT_TYPE,
                              CONTEXTUAL_USER_RESTRICTED, CONTEXTUAL_USER_CARDINALITY)}
OCL_OPERATORS = ("<", "<=", "=", "<>", ">", ">=")
_NEGATION = {"<": ">=", "<=": ">", "=": "<>", "<>": "=", ">": "<=", ">=": "<"}


def negate(op: str) -> str:
    """Toán tử phủ định: 'at most n' (<=) bị vi phạm khi > n."""
    return _NEGATION[op]


def witness_number(op: str, bound: float) -> float:
    """Một giá trị x thoả `x op bound` (dùng để dựng trạng thái chứng cứ cho USE)."""
    if op in (">", "<>"):
        return bound + 1
    if op == "<":
        return bound - 1
    return bound


def select_ip(p: Policy) -> InvariantPattern:
    """selectIP (Fig. 3): cấm mọi người dùng -> Restricted; giới hạn đếm -> Cardinality;
    tài nguyên có thuộc tính -> ObjectType; còn lại -> ContextualUser."""
    has_role = any(s.role for s in p.subjects)
    if p.decision == "deny" and not has_role:
        return CONTEXTUAL_USER_RESTRICTED
    if p.resource and p.resource.count is not None:
        return CONTEXTUAL_USER_CARDINALITY
    if p.resource and p.resource.attributes:
        return CONTEXTUAL_USER_OBJECT_TYPE
    return CONTEXTUAL_USER


def expected_executed(p: Policy) -> str:
    """Giá trị <OP>executed mà bất biến của policy đòi hỏi."""
    ip = select_ip(p)
    return ip.fixed_executed or ("true" if p.decision == "permit" else "false")
