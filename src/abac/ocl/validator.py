# -*- coding: utf-8 -*-
"""Kiểm tra cú pháp bất biến OCL ở mức nhẹ (W1).

Không thay thế USE: đây là bộ lọc nhanh để phát hiện lỗi cân bằng ngoặc,
dấu nháy, thiếu "context/inv/implies". W2–W3 sẽ chạy USE headless để kiểm
chứng cú pháp chính thức và ghi nhận tỷ lệ hợp lệ trong báo cáo.
"""
from __future__ import annotations

import re


def validate(text: str) -> list[str]:
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


def check_all(invariants: list[str]) -> dict:
    results = [validate(x) for x in invariants]
    return {
        "total": len(invariants),
        "valid": sum(1 for r in results if not r),
        "issues": {i: r for i, r in enumerate(results) if r},
    }
