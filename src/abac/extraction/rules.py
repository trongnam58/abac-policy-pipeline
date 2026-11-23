# -*- coding: utf-8 -*-
"""Mô-đun 1 — trích xuất thành phần chính sách ABAC theo ngữ cảnh (RCCP) từ câu EN.

Theo Fig. 1 của bài báo:
  identify_SubjectActionObject_attributes  -> detect_subjects / detect_actions / detect_resource
  identify_EnvironmentalContextual_conditions -> detect_environments / detect_conditions
Gazetteer (G) và trigger phrase (TF) là các từ điển bên dưới; nếu cài spaCy, gazetteer
được nạp vào EntityRuler và POS tagging lọc phân từ bổ ngữ (xem nlp.py).
"""
from __future__ import annotations

import re
from typing import Optional

from ..schema import Action, Condition, Environment, Policy, Resource, Subject
from . import nlp, vi_rules
from .common import detect_count, detect_duration, finalize, make_condition

VI_CHARS = re.compile(r"[ăâđêôơưĂÂĐÊÔƠƯ]")
VI_WORDS = re.compile(r"\b(sinh viên|giảng viên|hệ thống|không thể|có thể|trưởng khoa|phòng)\b")


def detect_language(text: str) -> str:
    """Nhận diện nhanh VI/EN: ký tự có dấu hoặc một số từ khoá tiếng Việt."""
    if VI_CHARS.search(text) or VI_WORDS.search(text.lower()):
        return "vi"
    return "en"


# ---------------------------------------------------------------------------
# Gazetteer + trigger phrase
# ---------------------------------------------------------------------------

_NOT_AGREEMENT = r"(?! agreements?| classes)"
# (regex, roles, membership, positions) — positions là các lựa chọn thay thế ("or")
ROLE_RULES = [
    (r"department['’]s academic coordinator and chair", ("academic_coordinator", "department_chair"), None, ()),
    (r"department['’]s academic coordinator", ("academic_coordinator",), None, ()),
    (r"head of educational testing and quality assurance", ("head_testing_qa",), None, ()),
    (r"head of academic affairs", ("head_academic_affairs",), None, ()),
    (r"users in the academic affairs or finance office", ("staff",), None,
     ("academic_affairs_office", "finance_office")),
    (r"users in the educational testing and quality assurance office", ("staff",), None, ("testing_qa_office",)),
    (r"users in the academic affairs office", ("staff",), None, ("academic_affairs_office",)),
    (r"^the finance office", ("staff",), None, ("finance_office",)),
    (r"civilian students?", ("student",), "civilian", ()),
    (r"retired visiting lecturers?" + _NOT_AGREEMENT, ("visiting_lecturer",), None, ("retired",)),
    (r"visiting lecturers?" + _NOT_AGREEMENT, ("visiting_lecturer",), None, ()),
    (r"department chairs?", ("department_chair",), None, ()),
    (r"course lecturers?|the course lecturer|\blecturers?" + _NOT_AGREEMENT, ("lecturer",), None, ()),
    (r"instructors?", ("instructor",), None, ()),
    (r"applicants?", ("applicant",), None, ()),
    (r"board of directors", ("board",), None, ()),
    (r"the director", ("director",), None, ()),
]
# "Users who are not in ..." — mọi người dùng thoả điều kiện (mẫu ContextualUserRestricted)
GENERIC_USERS = re.compile(r"^(?:all )?users who\b")

VERB_OPS = [
    ("view", "READ"), ("add", "CREATE"), ("update", "UPDATE"), ("modify", "UPDATE"),
    ("delete", "DELETE"), ("upload", "UPLOAD"), ("download", "DOWNLOAD"),
    ("create", "CREATE"), ("assign", "ASSIGN"), ("assess", "ASSESS"),
    ("accept", "ACCEPT"), ("deny", "DENY"), ("cancel", "CANCEL"),
    ("register", "REGISTER"), ("number", "NUMBER"), ("export", "EXPORT"),
    ("approve", "APPROVE"), ("comment", "COMMENT"), ("check", "CHECK"),
    ("retake", "RETAKE"), ("teach", "TEACH"), ("record", "RECORD"),
    ("issue", "ISSUE"), ("validate", "VALIDATE"), ("access", "READ"),
    ("considered valid", "VALIDATE"),
]
# phân từ đứng sau từ hạn định là bổ ngữ ("their issued agreements"), không phải hành động
_MODIFIER_PREFIX = re.compile(r"\b(?:the|their|its|a|an|all|of|own)\s+$")
_IMPLICIT_ACCESS = re.compile(r"\b(?:allowed|accessible|permitted)\b")

RESOURCE_RULES = [
    ("visiting lecturer agreements", "visiting_lecturer_agreement"),
    ("visiting lecturer classes", "visiting_lecturer_class"),
    ("preferred instructors", "instructor_preference"),
    ("graduation project topics", "graduation_project_topic"),
    ("list of civilian students", "student_list"),
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
    ("registration", "registration"),
    ("scores", "score"),
    ("rosters", "roster"),
    ("status", "status"),
    ("courses", "course"),
]
RESOURCE_RULES.sort(key=lambda x: len(x[0]), reverse=True)

SYSTEMS = {
    "learning management system": "learning_management_system",
    "academic information system": "academic_information_system",
    "course registration system": "course_registration_system",
    "visiting lecturer management system": "visiting_lecturer_management_system",
}
_JOINT_SYSTEMS = ("academic information and learning management systems",
                  ("academic_information_system", "learning_management_system"))

# trigger phrase cho điều kiện ngữ cảnh (thứ tự = ưu tiên)
CONDITION_PATTERNS = [
    (r"\bwith (?:the )?approval (?:of|from) (.*)$", "approval"),
    (r"\bwith (?:the )?(.+?)['’]s approval\b", "approval"),
    (r"\bonly if (.*)$", "restriction"),
    (r"\bonly when (.*)$", "restriction"),
    (r"\buntil (.*)$", "restriction"),
    (r"\bafter (.*)$", "precondition"),
    (r"\b(?:even )?if (.*)$", "condition"),
]
# phạm vi đứng sau tên hệ thống: "for courses that they are taking", "that are currently open"
_SCOPE = re.compile(
    r"^\s*(?:,\s*)?((?:only )?(?:for|across) .+?|(?:that|who|which) .+?)"
    r"(?=,| with | only (?:if|when|after)| if | even if | until | after | between |$)")
_SYSTEM_PHRASE = re.compile(
    r"(?:in|from) the [a-z ]*?(?:system|systems)\b")


def _gazetteer() -> dict[str, list[tuple[str, str]]]:
    resources = []
    for label, entity in RESOURCE_RULES:
        resources.append((label, entity))
        if label.endswith("s"):
            resources.append((label[:-1], entity))
    networks = list(SYSTEMS.items())
    return {"RESOURCE": resources, "NETWORK": networks}


nlp.configure(_gazetteer())


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
    if not m:
        m = re.search(r"\b(?:are|is|must|shall)\b", low)
    if m:
        return low[: m.start()], low[m.end():]
    return low, low


def detect_subjects(subject_text: str) -> list[Subject]:
    if GENERIC_USERS.search(subject_text.strip()):
        return [Subject(role="", entity_type="user")]
    out: list[Subject] = []
    seen: set[tuple[str, Optional[str]]] = set()
    for pattern, roles, membership, positions in ROLE_RULES:
        if not re.search(pattern, subject_text):
            continue
        for role in roles:
            for position in positions or (None,):
                if (role, position) not in seen:
                    seen.add((role, position))
                    out.append(Subject(role=role, membership=membership, position=position))
    roles = {s.role for s in out}
    if "visiting_lecturer" in roles:
        out = [s for s in out if s.role != "lecturer"]
        if any(s.position == "retired" for s in out):
            out = [s for s in out if s.role != "visiting_lecturer" or s.position]
    return out


def detect_logical_operator(subject_text: str, subjects: list[Subject]) -> str:
    """determineLogicalOperator (Fig. 3): 'or' khi chủ thể là các lựa chọn thay thế."""
    if len(subjects) > 1 and re.search(r"\bor\b", subject_text):
        return "or"
    return "and"


def detect_actions(action_text: str, ann: "nlp.Annotation | None" = None, offset: int = 0) -> list[Action]:
    # hành động nằm trước hệ thống và trước mệnh đề quan hệ ("that instructors have uploaded")
    clause = re.split(r" (?:in|from) the | (?:that|which|who) ", action_text)[0]
    found: list[tuple[int, str, str]] = []
    for verb, op in VERB_OPS:
        for m in re.finditer(r"\b" + verb + r"(?:s|ed|ing|d)?\b", clause):
            if _is_modifier(clause, m.start(), ann, offset):
                continue
            found.append((m.start(), verb, op))
            break
    found.sort(key=lambda x: x[0])
    out: list[Action] = []
    for _, verb, op in found:
        if all(a.operation != op for a in out):
            out.append(Action(verb=verb, operation=op))
    if not out and _IMPLICIT_ACCESS.search(action_text):
        out.append(Action(verb="access", operation="READ"))
    return out


def _is_modifier(clause: str, pos: int, ann: "nlp.Annotation | None", offset: int) -> bool:
    if ann is not None and (offset + pos) in ann.modifier_starts:
        return True
    return bool(_MODIFIER_PREFIX.search(clause[:pos])) and clause[pos:].split()[0].endswith("ed")


def _resource_regex(label: str) -> str:
    base = label[:-1] if label.endswith("s") else label
    return r"\b" + re.escape(base) + r"s?\b"


def _best_resource(text: str, start: int = 0):
    """Tài nguyên xuất hiện sớm nhất (trùng vị trí thì ưu tiên cụm dài hơn)."""
    best = None
    for label, entity in RESOURCE_RULES:
        m = re.compile(_resource_regex(label)).search(text, start)
        if m:
            key = (m.start(), -len(label))
            if best is None or key < best[0]:
                best = (key, label, entity)
    return best


def _best_resource_entity(ann: "nlp.Annotation", start: int):
    ents = sorted((s, -(e - s), eid) for label, eid, s, e in ann.entities
                  if label == "RESOURCE" and s >= start)
    if not ents:
        return None
    s, neg_len, eid = ents[0]
    label = next(lbl for lbl, ent in RESOURCE_RULES if ent == eid)
    return (s, neg_len), label, eid


def detect_resource(low: str, action_offset: int, ann: "nlp.Annotation | None" = None) -> Optional[Resource]:
    if ann is not None:
        best = _best_resource_entity(ann, action_offset) or _best_resource_entity(ann, 0)
    else:
        best = _best_resource(low, action_offset) or _best_resource(low)
    if best:
        return Resource(label=best[1], entity_type=best[2])
    return None


def detect_networks(low: str, ann: "nlp.Annotation | None" = None) -> list[str]:
    if _JOINT_SYSTEMS[0] in low:
        return list(_JOINT_SYSTEMS[1])
    if ann is not None:
        return list(dict.fromkeys(eid for label, eid, _, _ in sorted(
            ann.entities, key=lambda x: x[2]) if label == "NETWORK"))
    return [ns for phrase, ns in SYSTEMS.items() if phrase in low]


def detect_environments(sentence: str, ann: "nlp.Annotation | None" = None) -> list[Environment]:
    low = sentence.lower()
    envs = [Environment(id=f"env_{i + 1}", env_type="network", namespace=ns)
            for i, ns in enumerate(detect_networks(low, ann))]
    temporal = _detect_time_window(low)
    if temporal:
        envs.append(temporal)
    duration = detect_duration(low)
    if duration:
        envs.append(duration)
    period = re.search(r"\bwithin (?:the|a|one|each) (year|semester|month|week|day)\b", low)
    if period and not duration:
        envs.append(Environment(env_type="temporal", period=period.group(1),
                                trigger_phrase=period.group(0), raw=period.group(0)))
    for i, env in enumerate(envs):
        env.id = f"env_{i + 1}"
    return envs


def _detect_time_window(low: str) -> Optional[Environment]:
    m = re.search(r"between (\d{1,2}):(\d{2})\s*(am|pm)?\s*and (\d{1,2}):(\d{2})\s*(am|pm)", low)
    if not m:
        return None
    h1, m1, p1, h2, m2, p2 = m.groups()
    end = _to24(h2, m2, p2)
    start = _to24(h1, m1, p1 or p2)
    if not p1 and start > end:          # "8:00 and 5:00 pm" -> 08:00, không phải 20:00
        start = _to24(h1, m1, None)
    return Environment(env_type="temporal", trigger_phrase=m.group(0), raw=m.group(0),
                       time_from=start, time_to=end)


def _to24(h: str, mi: str, p: Optional[str]) -> str:
    hh = int(h)
    if p == "pm" and hh < 12:
        hh += 12
    if p == "am" and hh == 12:
        hh = 0
    return f"{hh:02d}:{mi}"


def detect_conditions(sentence: str, subject_text: str = "") -> list[Condition]:
    low = sentence.lower()
    out: list[Condition] = []
    who = re.search(r"\bwho (?:are |is )?(.+)$", subject_text.strip())
    if who:
        out.append(make_condition(who.group(1), "subject_scope"))
    scope = _detect_scope(low)
    if scope:
        out.append(scope)
    for pattern, kind in CONDITION_PATTERNS:
        m = re.search(pattern, low)
        if m and m.group(1).strip():
            out.append(make_condition(m.group(1), kind))
            break
    return out


def _detect_scope(low: str) -> Optional[Condition]:
    systems = list(_SYSTEM_PHRASE.finditer(low))
    if not systems:
        return None
    m = _SCOPE.match(low[systems[-1].end():])
    if not m:
        return None
    text = re.sub(r"^only ", "", m.group(1).strip())
    return make_condition(text, "scope")


# ---------------------------------------------------------------------------
# Điểm vào
# ---------------------------------------------------------------------------

def build_policy(pid: int, sentence: str) -> Policy:
    sentence = sentence.strip().rstrip(".")
    if detect_language(sentence) == "vi":
        return vi_rules.build_policy(pid, sentence)
    decision, modality = detect_decision(sentence)
    subject_text, action_text = split_subject_action(sentence)
    low = sentence.lower()
    offset = len(low) - len(action_text)
    ann = nlp.annotate(low)
    subjects = detect_subjects(subject_text)
    resource = detect_resource(low, offset, ann)
    count = detect_count(action_text)
    if resource and count:
        resource.count_operator, resource.count = count
    policy = Policy(
        id=pid,
        sentence=sentence,
        decision=decision,
        modality=modality,
        subjects=subjects,
        actions=detect_actions(action_text, ann, offset),
        resource=resource,
        environments=detect_environments(sentence, ann),
        conditions=detect_conditions(sentence, subject_text),
        logical_operator=detect_logical_operator(subject_text, subjects),
    )
    return finalize(policy)


def extract_texts(texts: list[str], start_id: int = 1) -> list[Policy]:
    out = []
    for text in texts:
        text = text.strip()
        if text:
            out.append(build_policy(start_id + len(out), text))
    return out
