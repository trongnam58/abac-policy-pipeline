# -*- coding: utf-8 -*-
"""Bộ luật trích xuất tiếng Việt (W2).

Cùng giao diện với rules tiếng Anh: build_policy(pid, sentence) -> Policy.
Phạm vi: câu "có thể / không thể / chỉ được phép", một–hai hành động, tài nguyên
thường gặp trong VACT-VI, môi trường mạng + thời gian, điều kiện if/only-if/
approval. Câu ghép phức tạp để nhánh LLM xử lý (xem llm.py).
"""
from __future__ import annotations

import re
from typing import Optional

from ..schema import Action, Condition, Environment, Policy, Resource, Subject
from .common import detect_count, detect_duration, finalize, make_condition

# ---------------------------------------------------------------------------
# Từ điển
# ---------------------------------------------------------------------------

# (regex, roles, membership, positions) — positions là các lựa chọn thay thế ("hoặc")
ROLE_RULES = [
    (r"người dùng thuộc phòng công tác học vụ hoặc (?:phòng )?tài chính", ("staff",), None,
     ("academic_affairs_office", "finance_office")),
    (r"người dùng thuộc phòng công tác học vụ", ("staff",), None, ("academic_affairs_office",)),
    (r"người dùng thuộc phòng khảo thí và bảo đảm chất lượng giáo dục", ("staff",), None, ("testing_qa_office",)),
    (r"^phòng tài chính", ("staff",), None, ("finance_office",)),
    (r"trưởng phòng khảo thí và bảo đảm chất lượng giáo dục", ("head_testing_qa",), None, ()),
    (r"trưởng phòng công tác học vụ", ("head_academic_affairs",), None, ()),
    (r"sinh viên dân sự", ("student",), "civilian", ()),
    (r"giảng viên thỉnh giảng đã nghỉ hưu", ("visiting_lecturer",), None, ("retired",)),
    (r"giảng viên thỉnh giảng(?! đã nghỉ hưu)", ("visiting_lecturer",), None, ()),
    (r"trưởng khoa", ("department_chair",), None, ()),
    (r"điều phối viên học vụ", ("academic_coordinator",), None, ()),
    (r"giảng viên phụ trách môn học", ("lecturer",), None, ()),
    (r"giảng viên hướng dẫn", ("instructor",), None, ()),
    (r"giảng viên", ("lecturer",), None, ()),
    (r"người nộp đơn", ("applicant",), None, ()),
    (r"ban giám đốc", ("board",), None, ()),
    (r"giám đốc", ("director",), None, ()),
]
# "Người dùng không thuộc ..." — mọi người dùng thoả điều kiện (ContextualUserRestricted)
GENERIC_USERS = re.compile(r"^(?:tất cả )?người dùng (không thuộc .+)$")

# (cụm từ, toán tử) — so khớp theo thứ tự xuất hiện trong câu
VERB_OPS = [
    ("xem", "READ"), ("thêm", "CREATE"), ("cập nhật", "UPDATE"), ("sửa", "UPDATE"),
    ("xóa", "DELETE"), ("tải lên", "UPLOAD"), ("tải xuống", "DOWNLOAD"),
    ("tạo", "CREATE"), ("gán", "ASSIGN"), ("đánh giá", "ASSESS"),
    ("chấp nhận", "ACCEPT"), ("từ chối", "DENY"), ("hủy", "CANCEL"),
    ("đăng ký", "REGISTER"), ("đánh số", "NUMBER"), ("xuất", "EXPORT"),
    ("phê duyệt", "APPROVE"), ("bình luận", "COMMENT"), ("kiểm tra", "CHECK"),
    ("học lại", "RETAKE"), ("giảng dạy", "TEACH"), ("ghi nhận", "RECORD"),
    ("cấp", "ISSUE"), ("xác thực", "VALIDATE"), ("hủy đăng ký", "CANCEL"),
    ("được coi là hợp lệ", "VALIDATE"),
]
VERB_OPS.sort(key=lambda x: len(x[0]), reverse=True)
# cụm không phải hành động (chứa động từ như "xuất", "đăng ký")
NON_ACTION = ("đề xuất", "đơn đăng ký", "kết quả đăng ký", "hệ thống đăng ký")
# phân từ làm bổ ngữ: "các môn học đã đăng ký", "đã được cấp", "đã tải lên"
_MODIFIER_PREFIX = re.compile(r"\bđã (?:được )?$")
_CLAUSE_END = re.compile(r" (?:trong|từ hệ thống|mà|sau khi|nếu|chỉ khi|cho đến khi|với sự|ngay cả khi) ")

# (cụm từ, entity_type)
RESOURCE_RULES = [
    ("hợp đồng giảng viên thỉnh giảng", "visiting_lecturer_agreement"),
    ("đề tài đồ án tốt nghiệp", "graduation_project_topic"),
    ("bài thi trắc nghiệm", "exam"),
    ("kết quả đăng ký môn học", "registration_result"),
    ("kết quả đăng ký", "registration_result"),
    ("tài liệu học tập", "learning_material"),
    ("danh sách lớp", "roster"),
    ("bảng điểm cuối kỳ", "grade"),
    ("điểm cuối kỳ", "grade"),
    ("bảng điểm", "transcript"),
    ("trạng thái đơn", "status"),
    ("thời khóa biểu", "class_schedule"),
    ("lịch giảng dạy", "teaching_schedule"),
    ("đề nghị mở môn học", "course_offering"),
    ("đơn", "application"),
    ("điểm", "score"),
    ("giảng viên hướng dẫn ưu tiên", "instructor_preference"),
    ("danh sách sinh viên dân sự", "student_list"),
    ("lớp của giảng viên thỉnh giảng", "visiting_lecturer_class"),
    ("đơn đăng ký", "application"),
    ("hủy đăng ký", "registration"),
    ("trạng thái", "status"),
    ("môn học", "course"),
]
RESOURCE_RULES.sort(key=lambda x: len(x[0]), reverse=True)

SYSTEMS = {
    "hệ thống thông tin học vụ": "academic_information_system",
    "hệ thống quản lý học tập": "learning_management_system",
    "hệ thống đăng ký môn học": "course_registration_system",
    "hệ thống quản lý giảng viên thỉnh giảng": "visiting_lecturer_management_system",
}

CONDITION_PATTERNS = [
    (r"với sự phê duyệt (?:của|từ) (.*)$", "approval"),
    (r"chỉ khi (.*)$", "restriction"),
    (r"chỉ nếu (.*)$", "restriction"),
    (r"cho đến khi (.*)$", "restriction"),
    (r"sau khi (.*)$", "precondition"),
    (r"ngay cả khi (.*)$", "condition"),
    (r"nếu (.*)$", "condition"),
]


# ---------------------------------------------------------------------------
# Trích xuất
# ---------------------------------------------------------------------------

def detect_decision(sentence: str) -> tuple[str, str]:
    low = sentence.lower()
    if re.search(r"\b(không thể|bị cấm|không được phép)\b", low):
        return "deny", "khong the"
    if re.search(r"chỉ được phép|được phép", low):
        return "permit", "duoc phep"
    return "permit", "co the"


def split_subject_action(sentence: str) -> tuple[str, str]:
    low = sentence.lower()
    passive = re.search(r"\b(?:chỉ )?được coi là\b", low)
    if passive:
        return low[: passive.start()], low[passive.start():]
    must = re.search(r"\bphải\b", low)
    if must and not re.search(r"\b(không thể|chỉ được phép|được phép|có thể)\b", low[: must.start()]):
        return low[: must.start()], low[must.end():]
    m = re.search(r"\b(không thể|chỉ được phép|được phép|có thể)\b", low)
    if m:
        return low[: m.start()], low[m.end():]
    return low, low


# cụm tài nguyên chứa tên vai trò ("hợp đồng giảng viên thỉnh giảng") không phải chủ thể
_RESOURCE_WITH_ROLE = re.compile(r"hợp đồng giảng viên thỉnh giảng|lịch giảng dạy")


def detect_subjects(subject_text: str) -> list[Subject]:
    subject_text = _RESOURCE_WITH_ROLE.sub("tài nguyên", subject_text)
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
    if any(s.role in ("visiting_lecturer", "instructor") for s in out):
        out = [s for s in out if s.role != "lecturer"]
    return out


def detect_logical_operator(subject_text: str, subjects: list[Subject]) -> str:
    """determineLogicalOperator (Fig. 3) cho câu tiếng Việt."""
    if len(subjects) > 1 and re.search(r"\bhoặc\b", subject_text):
        return "or"
    return "and"


def detect_actions(action_text: str, implicit_access: bool = False) -> list[Action]:
    clause = _CLAUSE_END.split(action_text)[0]
    taken: list[tuple[int, int]] = [(m.start(), m.end()) for phrase in NON_ACTION
                                    for m in re.finditer(re.escape(phrase), clause)]
    found: list[tuple[int, str, str]] = []
    for verb, op in VERB_OPS:            # cụm dài trước, không chồng lấn
        for m in re.finditer(r"\b" + re.escape(verb) + r"\b", clause):
            span = (m.start(), m.end())
            if any(a < span[1] and span[0] < b for a, b in taken):
                continue
            if _MODIFIER_PREFIX.search(clause[:m.start()]):
                continue
            taken.append(span)
            found.append((m.start(), verb, op))
    found.sort(key=lambda x: x[0])
    out: list[Action] = []
    for _, verb, op in found:
        if all(a.operation != op for a in out):
            out.append(Action(verb=verb, operation=op))
    if not out and implicit_access:
        out.append(Action(verb="truy cập", operation="READ"))
    return out


def _resource_regex(label: str) -> str:
    return r"\b" + re.escape(label) + r"\b"


def _best_resource(text: str):
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


def _start_time(h1: str, m1: str, p1: Optional[str], end: str, p2: Optional[str], to24) -> str:
    """Giờ bắt đầu không ghi buổi: kế thừa buổi của giờ kết thúc nếu vẫn <= giờ kết thúc."""
    start = to24(h1, m1, p1 or p2)
    if not p1 and start > end:
        start = to24(h1, m1, None)
    return start


def detect_environments(sentence: str) -> list[Environment]:
    low = sentence.lower()
    envs: list[Environment] = []
    for phrase, ns in SYSTEMS.items():
        if phrase in low:
            envs.append(Environment(id=f"env_{len(envs)+1}", env_type="network", namespace=ns))
    m = re.search(
        r"từ (\d{1,2}):(\d{2})\s*(sáng|chiều)?\s*đến (\d{1,2}):(\d{2})\s*(sáng|chiều)", low)
    duration = detect_duration(low)
    if duration:
        envs.append(duration)
    period = re.search(r"\btrong (?:một |mỗi )?(năm|học kỳ|tháng|tuần)\b", low)
    if period and not duration:
        envs.append(Environment(env_type="temporal", trigger_phrase=period.group(0), raw=period.group(0),
                                period={"năm": "year", "học kỳ": "semester", "tháng": "month",
                                        "tuần": "week"}[period.group(1)]))
    if m:
        h1, m1, p1, h2, m2, p2 = m.groups()

        def to24(h: str, mi: str, p: Optional[str]) -> str:
            hh = int(h)
            if p == "chiều" and hh < 12:
                hh += 12
            if p == "sáng" and hh == 12:
                hh = 0
            return f"{hh:02d}:{mi}"

        envs.append(Environment(
            id=f"env_{len(envs)+1}", env_type="temporal", trigger_phrase=m.group(0),
            time_from=_start_time(h1, m1, p1, to24(h2, m2, p2), p2, to24),
            time_to=to24(h2, m2, p2), raw=m.group(0)))
    for i, env in enumerate(envs):
        env.id = f"env_{i + 1}"
    return envs


_SCOPE = re.compile(r"^\s*(?:và [^,]*?)?\s*(?:chỉ )?(đối với .+?)"
                    r"(?=,| với sự| nếu| chỉ khi| cho đến khi| sau khi| trong khoảng| từ \d|$)")
_SYSTEM_PHRASE = re.compile(r"hệ thống (?:thông tin học vụ|quản lý học tập|đăng ký môn học"
                            r"|quản lý giảng viên thỉnh giảng)")


def detect_conditions(sentence: str, subject_text: str = "") -> list[Condition]:
    low = sentence.lower()
    out: list[Condition] = []
    generic = GENERIC_USERS.search(subject_text.strip())
    if generic:
        out.append(make_condition(generic.group(1), "subject_scope"))
    else:
        not_yet = re.search(r"\b(chưa [^,]+)$", subject_text.strip())
        if not_yet:
            out.append(make_condition(not_yet.group(1), "subject_scope"))
    systems = list(_SYSTEM_PHRASE.finditer(low))
    if systems:
        m = _SCOPE.match(low[systems[-1].end():])
        if m:
            out.append(make_condition(m.group(1), "scope"))
    for pattern, kind in CONDITION_PATTERNS:
        m = re.search(pattern, low)
        if m and m.group(1).strip():
            out.append(make_condition(m.group(1), kind))
            break
    return out


def build_policy(pid: int, sentence: str) -> Policy:
    sentence = sentence.strip().rstrip(".")
    decision, modality = detect_decision(sentence)
    subject_text, action_text = split_subject_action(sentence)
    subjects = detect_subjects(subject_text)
    resource = detect_resource(action_text, sentence.lower())
    count = detect_count(action_text)
    if resource and count:
        resource.count_operator, resource.count = count
    policy = Policy(
        id=pid,
        sentence=sentence,
        decision=decision,
        modality=modality,
        subjects=subjects,
        actions=detect_actions(action_text, implicit_access=modality == "duoc phep"),
        resource=resource,
        environments=detect_environments(sentence),
        conditions=detect_conditions(sentence, subject_text),
        logical_operator=detect_logical_operator(subject_text, subjects),
    )
    return finalize(policy)
