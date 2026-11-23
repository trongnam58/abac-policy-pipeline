# -*- coding: utf-8 -*-
"""Tiện ích dùng chung cho luật EN/VI: chuẩn hoá điều kiện và hậu xử lý policy."""
from __future__ import annotations

import re

from ..schema import Condition, Environment, Policy, Subject

# Vị trí (position) mặc định suy ra từ vai trò — bài báo dùng u.position='chair'
ROLE_POSITIONS = {"department_chair": "chair"}

# Cụm tham chiếu "khoa đó / that department" -> thuộc tính level của lớp tài nguyên
DEPARTMENT_SCOPE = re.compile(r"\bthat department\b|\bkhoa đó\b|\bcủa khoa\b")


def normalize(text: str) -> str:
    """'for that department’s courses' -> 'for_that_department'."""
    text = text.lower().strip().rstrip(".")
    text = re.sub(r"['’]s\s+\w+", "", text)        # bỏ sở hữu cách + danh từ theo sau
    text = re.sub(r"^only\s+", "", text)
    text = re.sub(r"[^\w]+", "_", text)
    return text.strip("_")


def make_condition(text: str, kind: str) -> Condition:
    text = text.strip().rstrip(".,")
    return Condition(text=text, kind=kind, normalized=normalize(text))


def finalize(policy: Policy) -> Policy:
    """Gán position mặc định theo vai trò và thuộc tính level cho tài nguyên."""
    policy.subjects = [_with_position(s) for s in policy.subjects]
    if policy.resource and any(
            DEPARTMENT_SCOPE.search(c.text.lower()) for c in policy.conditions
            if c.kind == "scope"):
        policy.resource.attributes.setdefault("level", "department")
    return policy


def _with_position(s: Subject) -> Subject:
    if not s.position and s.role in ROLE_POSITIONS:
        return Subject(role=s.role, entity_type=s.entity_type,
                       membership=s.membership, position=ROLE_POSITIONS[s.role])
    return s


# (regex, toán tử OCL) — thứ tự quan trọng: cụm dài trước
DURATION_OPERATORS = [
    (r"no more than|not more than|up to|at most|tối đa|không quá", "<="),
    (r"more than|exceed(?:s|ing)?|over|vượt quá|quá|hơn", ">"),
    (r"at least|tối thiểu|ít nhất", ">="),
    (r"less than|fewer than|dưới|ít hơn", "<"),
    (r"exactly|đúng", "="),
]
TIME_UNITS = {
    "second": "seconds", "minute": "minutes", "hour": "hours", "day": "days",
    "month": "months", "year": "years",
    "giây": "seconds", "phút": "minutes", "giờ": "hours", "ngày": "days",
    "tháng": "months", "năm": "years",
}
PERIODS = {"năm": "year", "tháng": "month", "tuần": "week", "ngày": "day"}

_OPS = "|".join(p for p, _ in DURATION_OPERATORS)
_DURATION_EN = re.compile(
    rf"\b({_OPS})\s+(\d+(?:\.\d+)?)\s+(second|minute|hour|day|month|year)s?"
    r"(?:\s+(?:per|a|each|every)\s+(year|month|week|day))?")
_DURATION_VI = re.compile(
    rf"({_OPS})\s+(\d+(?:[.,]\d+)?)\s+(giây|phút|giờ|ngày|tháng|năm)"
    r"(?:\s*(?:mỗi|một|/|trong một|trong mỗi)\s*(năm|tháng|tuần|ngày))?")


NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10,
    "một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5, "sáu": 6, "bảy": 7, "tám": 8,
    "chín": 9, "mười": 10,
}
_TIME_WORDS = r"(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?|giây|phút|giờ|ngày|tuần|tháng|năm)\b"
_COUNT = re.compile(
    rf"(?<!\w)({_OPS})\s+(\d+|{'|'.join(NUMBER_WORDS)})\s+(?!{_TIME_WORDS})(?=[^\W\d])")


def detect_count(text: str) -> tuple[str, int] | None:
    """'at most one graduation project topic' -> ('<=', 1); bỏ qua thời lượng ('560 hours')."""
    m = _COUNT.search(text)
    if not m:
        return None
    raw = m.group(2)
    return ocl_operator(m.group(1)), int(raw) if raw.isdigit() else NUMBER_WORDS[raw]


def ocl_operator(phrase: str) -> str:
    """determineOCLoperator (Fig. 3): cụm so sánh -> toán tử OCL."""
    for pattern, op in DURATION_OPERATORS:
        if re.fullmatch(pattern, phrase.strip()):
            return op
    return "="


def detect_duration(low: str) -> Environment | None:
    """'more than 560 hours per year' -> Environment(duration, >, 560, hours, year)."""
    m = _DURATION_EN.search(low) or _DURATION_VI.search(low)
    if not m:
        return None
    phrase, value, unit, period = m.groups()
    return Environment(
        id="env_duration", env_type="duration", trigger_phrase=m.group(0), raw=m.group(0),
        operator=ocl_operator(phrase), value=float(value.replace(",", ".")),
        unit=TIME_UNITS[unit], period=PERIODS.get(period, period))
