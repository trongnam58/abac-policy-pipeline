# -*- coding: utf-8 -*-
"""Siêu mô hình ABAC theo ngữ cảnh (rút gọn theo bài báo gốc).

9 lớp UML và 11 kiểu liệt kê; giữ nguyên cấu trúc để W2/W3 dựng mô hình
`.use` / `.puml` nhất quán với báo cáo.
"""
from __future__ import annotations

CLASSES = [
    "User", "Group", "Subject", "Object", "Action", "Environment",
    "Context", "ObjectType", "Natural_Language_Policy_Statement",
]

ENUMS = {
    "Role": [
        "student", "lecturer", "department_chair", "academic_coordinator",
        "head_testing_qa", "head_academic_affairs", "applicant", "instructor",
        "visiting_lecturer", "staff", "board", "director",
    ],
    "Network": [
        "learning_management_system", "academic_information_system",
        "course_registration_system", "visiting_lecturer_management_system",
    ],
    "Device": ["desktop", "laptop", "mobile"],
    "TimeUnit": ["seconds", "minutes", "hours", "days", "months", "years"],
    "DistanceUnit": ["meters", "kilometers", "miles"],
    "DayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "ConstraintType": ["TemporalConstraint", "SpatialConstraint"],
    "ORG": ["academic_affairs_office", "testing_qa_office", "finance_office"],
    "FAC": ["campus", "building", "lab"],
    "LOC": ["room", "floor"],
    "GPE": ["vietnam", "hanoi"],
}

# Ánh xạ role nội bộ -> giá trị enum Role (dùng khi sinh OCL/UML)
def role_enum_name(role: str) -> str:
    return role if role in ENUMS["Role"] else "student"
