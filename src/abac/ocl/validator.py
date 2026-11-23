# -*- coding: utf-8 -*-
"""Kiểm tra bất biến OCL trước khi đưa vào USE.

- validate(text): kiểm tra cú pháp nhẹ (context/inv/implies, ngoặc, nháy, executed=...).
- validate(text, model): thêm kiểm tra ngữ nghĩa với mô hình biểu diễn — mọi thuộc
  tính, vai trò điều hướng, lớp và enum literal được tham chiếu phải tồn tại.
Kiểm chứng chính thức bằng USE: xem use_runner.py.
"""
from __future__ import annotations

import re

from ..modeling.use_model import RepresentationModel

_CONTEXT_ATTR = re.compile(r"(?:^|\(|\bor |\band )\s*([A-Za-z]\w*)\s*(?:<=|>=|<>|=|<|>)")


def validate(text: str, model: RepresentationModel | None = None) -> list[str]:
    issues = _syntax_issues(text)
    if model is not None:
        issues += _semantic_issues(text, model)
    return issues


def _syntax_issues(text: str) -> list[str]:
    issues: list[str] = []
    if not re.search(r"\bcontext\s+\w+\s+inv\s+\w+\s*:", text):
        issues.append("thiếu mẫu 'context <Class> inv <name>:'")
    if "implies" not in text:
        issues.append("thiếu 'implies'")
    if text.count("(") != text.count(")"):
        issues.append("ngoặc tròn không cân bằng")
    if text.count("'") % 2 != 0:
        issues.append("dấu nháy đơn lẻ")
    if not re.search(r"executed\s*=\s*(true|false)\s*$", text):
        issues.append("không kết thúc bằng executed=true/false")
    return issues


def _semantic_issues(text: str, model: RepresentationModel) -> list[str]:
    issues: list[str] = []
    literals = {v for values in model.enums.values() for v in values}
    for lit in re.findall(r"#(\w+)", text):
        if lit not in literals:
            issues.append(f"enum literal không tồn tại: #{lit}")
    for attr in re.findall(r"actions\.(\w+executed)\b", text):
        if attr not in model.attribute_names("Action"):
            issues.append(f"Action không có thuộc tính {attr}")
    for attr in re.findall(r"\bu\.(\w+)", text):
        if attr != "subject" and attr not in model.attribute_names("User"):
            issues.append(f"User không có thuộc tính {attr}")
    for role in re.findall(r"objects\.(\w+)->", text):
        if role not in model.resource_classes.values():
            issues.append(f"Object không có vai trò điều hướng {role}")
    for cls in re.findall(r"(\w+)\.allInstances", text):
        if cls not in model.classes:
            issues.append(f"lớp không tồn tại: {cls}")
    antecedent = text.split(":", 1)[-1].split("implies")[0]
    antecedent = re.sub(r"\w+\.allInstances\(\)->forAll\(.*", "", antecedent, flags=re.S)
    for attr in _CONTEXT_ATTR.findall(antecedent):
        if attr not in model.attribute_names("Context"):
            issues.append(f"Context không có thuộc tính {attr}")
    return issues


def check_all(invariants: list[str], model: RepresentationModel | None = None) -> dict:
    results = [validate(x, model) for x in invariants]
    return {
        "total": len(invariants),
        "valid": sum(1 for r in results if not r),
        "issues": {i: r for i, r in enumerate(results) if r},
    }
