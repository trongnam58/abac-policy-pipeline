# -*- coding: utf-8 -*-
"""Ba mẫu IP (invariant pattern) của mô-đun 3.

Dùng làm tài liệu tham chiếu và là khuôn sinh bất biến; nội dung bám theo
bài báo gốc:
  - ContextualUser            : kiểm tra quyền thực thi theo thuộc tính User + Context
  - ContextualUserObjectType  : thêm ràng buộc trên ObjectType (tài nguyên phi con người)
  - ContextualUserRestricted  : cấm thực thi (executed = false)
"""
from __future__ import annotations

CONTEXTUAL_USER = """context Context inv {name}:
  {condition_lines}
  implies environments.actions->exists(namesAction='{action}')
        and actions.{action}executed={executed}"""

CONTEXTUAL_USER_OBJECT = """context Context inv {name}:
  {condition_lines}
  and Object.allInstances()->forAll(o | o.label='{object_label}')
  implies environments.actions->exists(namesAction='{action}')
        and actions.{action}executed={executed}"""

CONTEXTUAL_USER_RESTRICTED = """context Context inv {name}:
  {condition_lines}
  and Object.allInstances()->forAll(o | o.label='{object_label}' and
        o.isNonHumanResource=true)
  implies environments.actions->exists(namesAction='{action}')
        and actions.{action}executed=false"""

PATTERNS = {
    "ContextualUser": CONTEXTUAL_USER,
    "ContextualUserObjectType": CONTEXTUAL_USER_OBJECT,
    "ContextualUserRestricted": CONTEXTUAL_USER_RESTRICTED,
}
