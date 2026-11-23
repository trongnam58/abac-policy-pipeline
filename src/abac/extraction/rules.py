# -*- coding: utf-8 -*-
"""Baseline trích xuất bằng luật (rules) — W1.

Mục tiêu của bản W1: chạy được trên 100 câu VACT tiếng Anh, sinh JSON đúng
schema. Bản W2 sẽ bổ sung nhánh LLM (xem llm.py) cho câu phủ định / mệnh đề
ghép và so sánh 3 cấu hình rules / LLM / lai.
"""
from __future__ import annotations

import re
from typing import Optional

from ..schema import Action, Condition, Environment, Policy, Resource, Subject
from . import vi_rules

VI_CHARS = re.compile(r"[ăâđêôơưĂÂĐÊÔƠƯ]")
VI_WORDS = re.compile(r"\b(sinh viên|giảng viên|hệ thống|không thể|có thể|trưởng khoa|phòng)\b")


def detect_language(text: str) -> str:
    """Nhận diện nhanh VI/EN: ký tự có dấu hoặc một số từ khoá tiếng Việt."""
    if VI_CHARS.search(text) or VI_WORDS.search(text.lower()):
        return "vi"
    return "en"


# ---------------------------------------------------------------------------
# Từ điển
# ---------------------------------------------------------------------------

# (regex, role, membership, position)
ROLE_RULES = [
    (r"department['’]s academic coordinator and chair", ("academic_coordinator", "department_chair"), None, None),
    (r"department['’]s academic coordinator", ("academic_coordinator",), None, None),
    (r"head of educational testing and quality assurance", ("head_testing_qa",), None, None),
    (r"head of academic affairs", ("head_academic_affairs",), None, None),
    (r"users in the academic affairs or finance office", ("staff",), None, "academic_affairs_or_finance_office"),
    (r"users in the educational testing and quality assurance office", ("staff",), None, "testing_qa_office"),
    (r"users in the academic affairs office", ("staff",), None, "academic_affairs_office"),
    (r"users who are not in the academic affairs office", ("staff",), None, "not_academic_affairs_office"),
    (r"civilian students?", ("student",), "civilian", None),
    (r"retired visiting lecturers?", ("visiting_lecturer",), None, "retired"),
    (r"visiting lecturers?", ("visiting_lecturer",), None, None),
    (r"department chairs?", ("department_chair",), None, None),
    (r"course lecturers?|the course lecturer|lecturers?", ("lecturer",), None, None),
    (r"instructors?", ("instructor",), None, None),
    (r"applicants?", ("applicant",), None, None),
    (r"board of directors", ("board",), None, None),
    (r"the director", ("director",), None, None),
]

# (verb, operation)
VERB_OPS = [
    ("view", "READ"), ("add", "CREATE"), ("update", "UPDATE"), ("modify", "UPDATE"),
    ("delete", "DELETE"), ("upload", "UPLOAD"), ("download", "DOWNLOAD"),
    ("create", "CREATE"), ("assign", "ASSIGN"), ("assess", "ASSESS"),
    ("accept", "ACCEPT"), ("deny", "DENY"), ("cancel", "CANCEL"),
    ("register", "REGISTER"), ("number", "NUMBER"), ("export", "EXPORT"),
    ("approve", "APPROVE"), ("comment", "COMMENT"), ("check", "CHECK"),
    ("retake", "RETAKE"), ("teach", "TEACH"), ("record", "RECORD"),
    ("issue", "ISSUE"), ("validate", "VALIDATE"),
]

# (label, entity_type) — sắp theo độ dài giảm dần để ưu tiên cụm dài
RESOURCE_RULES = [
    ("visiting lecturer agreements", "visiting_lecturer_agreement"),
    ("graduation project topics", "graduation_project_topic"),
    ("multiple-choice exams", "exam"),
    ("course registration results", "registration_result"),
    ("learning materials", "learning_material"),
    ("registration results", "registration_result"),
    ("class schedules", "class_schedule"),
    ("teaching schedules", "teaching_schedule"),
    ("course rosters", "roster"),
    ("final grades", "grade"),
    ("course offering", "course_offering"),
    ("transcripts", "transcript"),
    ("applications", "application"),
    ("scores", "score"),
    ("rosters", "roster"),
    ("status", "status"),
]
RESOURCE_RULES.sort(key=lambda x: len(x[0]), reverse=True)

# namespace -> mô tả hệ thống
SYSTEMS = {
    "learning management system": "learning_management_system",
    "academic information system": "academic_information_system",
    "course registration system": "course_registration_system",
    "visiting lecturer management system": "visiting_lecturer_management_system",
}

CONDITION_PATTERNS = [
    (r"\bwith (?:the )?approval (?:of|from) (.*)$", "approval"),
    (r"\bonly if (.*)$", "restriction"),
    (r"\bonly when (.*)$", "restriction"),
    (r"\buntil (.*)$", "restriction"),
    (r"\bafter (.*)$", "precondition"),
    (r"\bif (.*)$", "condition"),
    (r"\bonly for (.*)$", "scope"),
]


# ---------------------------------------------------------------------------
# Trích xuất từng thành phần
# ---------------------------------------------------------------------------

def detect_decision(sentence: str) -> tuple[str, str]:
    low = sentence.lower()
    if re.search(r"\b(cannot|can not|can't|not allowed|not permitted|prohibited)\b", low):
        return "deny", "cannot"
    if re.search(r"\bcan only\b", low):
        return "permit", "can only"
    return "permit", "can"


def split_subject_action(sentence: str) -> tuple[str, str]:
    low = sentence.lower()
    m = re.search(r"\b(cannot|can not|can't|can only|can)\b", low)
    if m:
        return low[: m.start()], low[m.end():]
    m = re.search(r"\b(?:are|is|must|shall)\b", low)
    if m:
        return low[: m.start()], low[m.end():]
    return low, low


def detect_subjects(subject_text: str) -> list[Subject]:
    out: list[Subject] = []
    seen = set()
    for pattern, roles, membership, position in ROLE_RULES:
        if re.search(pattern, subject_text):
            for role in roles:
                if role not in seen:
                    seen.add(role)
                    out.append(Subject(role=role, membership=membership, position=position))
    # "visiting lecturer" đã bao hàm "lecturer": bỏ vai trò chung để không trùng
    roles = [s.role for s in out]
    if "visiting_lecturer" in roles and "lecturer" in roles:
        out = [s for s in out if s.role != "lecturer"]
    return out


def detect_actions(action_text: str) -> list[Action]:
    clause = action_text.split(" in the ")[0]
    found: list[tuple[int, str, str]] = []
    for verb, op in VERB_OPS:
        m = re.search(r"\b" + verb + r"(?:s|ed|ing)?\b", clause)
        if m:
            found.append((m.start(), verb, op))
    found.sort(key=lambda x: x[0])
    return [Action(verb=verb, operation=op) for _, verb, op in found]


def _resource_regex(label: str) -> str:
    base = label[:-1] if label.endswith("s") else label
    return r"\b" + re.escape(base) + r"s?\b"


def _best_resource(text: str):
    """Chọn tài nguyên xuất hiện sớm nhất (trùng vị trí thì ưu tiên cụm dài hơn)."""
    best = None
    for label, entity in RESOURCE_RULES:
        m = re.search(_resource_regex(label), text)
        if m:
            key = (m.start(), -len(label))
            if best is None or key < best[0]:
                best = (key, label, entity)
    return best


def detect_resource(action_text: str, full: str) -> Optional[Resource]:
    best = _best_resource(action_text) or _best_resource(full)
    if best:
        return Resource(label=best[1], entity_type=best[2])
    return None


def detect_environments(sentence: str) -> list[Environment]:
    low = sentence.lower()
    envs: list[Environment] = []
    if "academic information and learning management systems" in low:
        for ns in ("academic_information_system", "learning_management_system"):
            envs.append(Environment(id=f"env_{len(envs)+1}", env_type="network", namespace=ns))
    else:
        for phrase, ns in SYSTEMS.items():
            if phrase in low:
                envs.append(Environment(id=f"env_{len(envs)+1}", env_type="network", namespace=ns))
    m = re.search(
        r"between (\d{1,2}):(\d{2})\s*(am|pm)?\s*and (\d{1,2}):(\d{2})\s*(am|pm)", low)
    if m:
        h1, m1, p1, h2, m2, p2 = m.groups()
        def to24(h: str, mi: str, p: str) -> str:
            hh = int(h)
            if p:
                if p == "pm" and hh < 12:
                    hh += 12
                if p == "am" and hh == 12:
                    hh = 0
            return f"{hh:02d}:{mi}"
        envs.append(Environment(
            id=f"env_{len(envs)+1}", env_type="temporal", trigger_phrase=m.group(0),
            time_from=to24(h1, m1, p1), time_to=to24(h2, m2, p2), raw=m.group(0)))
    return envs


def detect_conditions(sentence: str) -> list[Condition]:
    low = sentence.lower()
    for pattern, kind in CONDITION_PATTERNS:
        m = re.search(pattern, low)
        if m:
            text = m.group(1).strip().rstrip(".")
            if text:
                return [Condition(text=text, kind=kind)]
    return []


# ---------------------------------------------------------------------------
# Điểm vào
# ---------------------------------------------------------------------------

def build_policy(pid: int, sentence: str) -> Policy:
    sentence = sentence.strip().rstrip(".")
    if detect_language(sentence) == "vi":
        return vi_rules.build_policy(pid, sentence)
    decision, modality = detect_decision(sentence)
    subject_text, action_text = split_subject_action(sentence)
    return Policy(
        id=pid,
        sentence=sentence,
        decision=decision,
        modality=modality,
        subjects=detect_subjects(subject_text),
        actions=detect_actions(action_text),
        resource=detect_resource(action_text, sentence.lower()),
        environments=detect_environments(sentence),
        conditions=detect_conditions(sentence),
    )


def extract_texts(texts: list[str], start_id: int = 1) -> list[Policy]:
    out = []
    for i, text in enumerate(texts):
        text = text.strip()
        if not text:
            continue
        out.append(build_policy(start_id + len(out), text))
    return out
