# -*- coding: utf-8 -*-
"""Prompt few-shot cho nhánh LLM (W2).

Mục tiêu: với câu khó (phủ định lồng nhau, mệnh đề ghép, đại từ), LLM trả về
JSON đúng schema của `abac.schema.Policy` để validator kiểm tra trước khi gộp.
"""
from __future__ import annotations

import json

SCHEMA_HINT = """{
  "id": 1,
  "sentence": "...",
  "decision": "permit" | "deny",
  "modality": "can" | "cannot" | "can only",
  "subjects": [{"role": "...", "entity_type": "user", "membership": "..."|null, "position": "..."|null}],
  "actions": [{"verb": "...", "operation": "READ|CREATE|UPDATE|DELETE|UPLOAD|DOWNLOAD|ASSIGN|ASSESS|ACCEPT|DENY|CANCEL|REGISTER|NUMBER|EXPORT|APPROVE|COMMENT|CHECK|RETAKE|TEACH|RECORD|ISSUE|VALIDATE"}],
  "resource": {"label": "...", "entity_type": "..."}|null,
  "environments": [{"id": "env_1", "env_type": "network|temporal", "namespace": "...|null", "trigger_phrase": "...|null", "time_from": "HH:MM|null", "time_to": "HH:MM|null"}],
  "conditions": [{"text": "...", "kind": "condition|restriction|approval|precondition|scope"}]
}"""

SYSTEM = (
    "Bạn là bộ trích xuất chính sách ABAC từ câu ngôn ngữ tự nhiên (tiếng Việt hoặc tiếng Anh). "
    "Chỉ trả về MỘT đối tượng JSON đúng schema, không thêm giải thích, không markdown. "
    "Nếu một thành phần không xuất hiện trong câu, để null hoặc mảng rỗng; không bịa thêm."
)

EXAMPLES = [
    (
        "Civilian students cannot register for courses in the course registration system "
        "if the system has not been activated.",
        {
            "decision": "deny",
            "modality": "cannot",
            "subjects": [{"role": "student", "entity_type": "user", "membership": "civilian", "position": None}],
            "actions": [{"verb": "register", "operation": "REGISTER"}],
            "resource": None,
            "environments": [{"id": "env_1", "env_type": "network",
                              "namespace": "course_registration_system",
                              "trigger_phrase": None, "time_from": None, "time_to": None}],
            "conditions": [{"text": "the system has not been activated", "kind": "condition"}],
        },
    ),
    (
        "Sinh viên dân sự có thể đăng ký đề tài đồ án tốt nghiệp chỉ khi hệ thống được kích hoạt.",
        {
            "decision": "permit",
            "modality": "co the",
            "subjects": [{"role": "student", "entity_type": "user", "membership": "civilian", "position": None}],
            "actions": [{"verb": "đăng ký", "operation": "REGISTER"}],
            "resource": {"label": "đề tài đồ án tốt nghiệp", "entity_type": "graduation_project_topic"},
            "environments": [],
            "conditions": [{"text": "hệ thống được kích hoạt", "kind": "restriction"}],
        },
    ),
]


def build_messages(sentence: str, language: str = "auto") -> list[dict]:
    lang = "tiếng Việt" if language == "vi" else "tiếng Anh" if language == "en" else "tiếng Việt hoặc tiếng Anh"
    messages = [{"role": "system", "content": SYSTEM}]
    for ex_sentence, ex_json in EXAMPLES:
        messages.append({"role": "user", "content": ex_sentence})
        messages.append({"role": "assistant", "content": json.dumps(ex_json, ensure_ascii=False)})
    messages.append({
        "role": "user",
        "content": (
            f"Trích xuất chính sách ABAC từ câu {lang} sau thành JSON đúng schema "
            f"(schema tham chiếu: {SCHEMA_HINT}).\n\nCâu: {sentence}"
        ),
    })
    return messages


def build_prompt_text(sentence: str, language: str = "auto") -> str:
    """Bản một chuỗi (dùng cho log/debug hoặc API không hỗ trợ messages)."""
    parts = [SYSTEM]
    for ex_sentence, ex_json in EXAMPLES:
        parts.append(f"USER: {ex_sentence}")
        parts.append(f"ASSISTANT: {json.dumps(ex_json, ensure_ascii=False)}")
    parts.append(f"USER: {build_messages(sentence, language)[-1]['content']}")
    return "\n\n".join(parts)
