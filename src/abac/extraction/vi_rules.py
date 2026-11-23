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

# ---------------------------------------------------------------------------
# Từ điển
# ---------------------------------------------------------------------------

ROLE_RULES = [
    (r"người dùng không thuộc phòng công tác học vụ", ("staff",), None, "not_academic_affairs_office"),
    (r"người dùng thuộc phòng công tác học vụ", ("staff",), None, "academic_affairs_office"),
    (r"người dùng thuộc phòng khảo thí và bảo đảm chất lượng giáo dục", ("staff",), None, "testing_qa_office"),
    (r"người dùng thuộc phòng (?:công tác học vụ|tài chính)", ("staff",), None, "office"),
    (r"trưởng phòng khảo thí và bảo đảm chất lượng giáo dục", ("head_testing_qa",), None, None),
    (r"trưởng phòng công tác học vụ", ("head_academic_affairs",), None, None),
    (r"sinh viên dân sự", ("student",), "civilian", None),
    (r"giảng viên thỉnh giảng đã nghỉ hưu", ("visiting_lecturer",), None, "retired"),
    (r"giảng viên thỉnh giảng", ("visiting_lecturer",), None, None),
    (r"trưởng khoa", ("department_chair",), None, None),
    (r"điều phối viên học vụ", ("academic_coordinator",), None, None),
    (r"giảng viên phụ trách môn học", ("lecturer",), None, None),
    (r"giảng viên", ("lecturer",), None, None),
    (r"người nộp đơn", ("applicant",), None, None),
    (r"ban giám đốc", ("board",), None, None),
    (r"giám đốc", ("director",), None, None),
]

# (cụm từ, toán tử) — so khớp theo thứ tự xuất hiện trong câu
VERB_OPS = [
    ("xem", "READ"), ("thêm", "CREATE"), ("cập nhật", "UPDATE"), ("sửa", "UPDATE"),
    ("xóa", "DELETE"), ("tải lên", "UPLOAD"), ("tải xuống", "DOWNLOAD"),
    ("tạo", "CREATE"), ("gán", "ASSIGN"), ("đánh giá", "ASSESS"),
    ("chấp nhận", "ACCEPT"), ("từ chối", "DENY"), ("hủy", "CANCEL"),
    ("đăng ký", "REGISTER"), ("đánh số", "NUMBER"), ("xuất", "EXPORT"),
    ("phê duyệt", "APPROVE"), ("bình luận", "COMMENT"), ("kiểm tra", "CHECK"),
    ("học lại", "RETAKE"), ("giảng dạy", "TEACH"), ("ghi nhận", "RECORD"),
    ("cấp", "ISSUE"), ("xác thực", "VALIDATE"),
]

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
    (r"chỉ đối với (.*)$", "scope"),
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
    m = re.search(r"\b(không thể|chỉ được phép|được phép|có thể)\b", low)
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
    roles = [s.role for s in out]
    if "visiting_lecturer" in roles and "lecturer" in roles:
        out = [s for s in out if s.role != "lecturer"]
    return out


def detect_actions(action_text: str) -> list[Action]:
    clause = action_text.split(" trong ")[0]
    found: list[tuple[int, str, str]] = []
    for verb, op in VERB_OPS:
        m = re.search(r"\b" + re.escape(verb) + r"\b", clause)
        if m:
            found.append((m.start(), verb, op))
    found.sort(key=lambda x: x[0])
    # khử trùng theo toán tử, giữ lần xuất hiện đầu
    out: list[Action] = []
    seen_ops = set()
    for _, verb, op in found:
        if op not in seen_ops:
            seen_ops.add(op)
            out.append(Action(verb=verb, operation=op))
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


def detect_environments(sentence: str) -> list[Environment]:
    low = sentence.lower()
    envs: list[Environment] = []
    for phrase, ns in SYSTEMS.items():
        if phrase in low:
            envs.append(Environment(id=f"env_{len(envs)+1}", env_type="network", namespace=ns))
    m = re.search(
        r"từ (\d{1,2}):(\d{2})\s*(sáng|chiều)?\s*đến (\d{1,2}):(\d{2})\s*(sáng|chiều)", low)
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


def build_policy(pid: int, sentence: str) -> Policy:
    sentence = sentence.strip().rstrip(".")
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
