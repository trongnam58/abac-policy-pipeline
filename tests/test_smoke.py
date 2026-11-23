# -*- coding: utf-8 -*-
"""Smoke test cho pipeline W1–W2 — chạy: python tests/test_smoke.py"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from abac.extraction import prompts                    # noqa: E402
from abac.extraction.client import parse_json_object    # noqa: E402
from abac.extraction.llm import enrich_with_llm, merge  # noqa: E402
from abac.extraction.pipeline import extract           # noqa: E402
from abac.extraction.rules import detect_language      # noqa: E402
from abac.modeling import puml, use_model              # noqa: E402
from abac.ocl import generator, validator              # noqa: E402

EN = [
    "Civilian students can view rosters in the learning management system for courses that they are taking.",
    "Civilian students cannot register for courses in the course registration system if the system has not been activated.",
    "A department chair can view and download the transcripts of all civilian students in the academic information system for that department.",
]
VI = [
    "Sinh viên dân sự có thể xem danh sách lớp trong hệ thống quản lý học tập đối với các môn học mà họ đang theo học.",
    "Sinh viên dân sự không thể đăng ký môn học trong hệ thống đăng ký môn học nếu hệ thống chưa được kích hoạt.",
    "Trưởng khoa có thể xem và tải xuống bảng điểm của tất cả sinh viên dân sự trong hệ thống thông tin học vụ đối với khoa đó.",
]


def test_extract_en():
    ds = extract(EN)
    assert len(ds.policies) == 3
    p1, p2, p3 = ds.policies
    assert p1.decision == "permit" and p1.subjects[0].role == "student"
    assert p1.subjects[0].membership == "civilian"
    assert {a.operation for a in p1.actions} == {"READ"}
    assert p1.resource is not None and p1.resource.entity_type == "roster"
    assert any(e.namespace == "learning_management_system" for e in p1.environments)
    assert p2.decision == "deny" and p2.conditions and "activated" in p2.conditions[0].text
    assert {a.operation for a in p3.actions} == {"READ", "DOWNLOAD"}


def test_extract_vi():
    ds = extract(VI)
    p1, p2, p3 = ds.policies
    assert p1.decision == "permit"
    assert p1.subjects and p1.subjects[0].role == "student"
    assert {a.operation for a in p1.actions} == {"READ"}
    assert p1.resource and p1.resource.entity_type == "roster"
    assert [e.namespace for e in p1.environments] == ["learning_management_system"]
    assert p2.decision == "deny"
    assert {a.operation for a in p2.actions} == {"REGISTER"}
    assert [e.namespace for e in p2.environments] == ["course_registration_system"]
    assert {a.operation for a in p3.actions} == {"READ", "DOWNLOAD"}
    assert p3.resource and p3.resource.entity_type == "transcript"


def test_language_detection():
    assert detect_language(VI[0]) == "vi"
    assert detect_language(EN[0]) == "en"


def test_generate_and_validate():
    ds = extract(EN)
    invs = []
    for p in ds.policies:
        invs.extend(generator.generate(p))
    assert len(invs) == 4
    check = validator.check_all(invs)
    assert check["valid"] == check["total"], check


def test_writers():
    ds = extract(EN[:1])
    text = puml.policy_to_puml(ds.policies[0])
    assert text.startswith("@startuml") and text.endswith("@enduml")
    use_text = use_model.dataset_to_use(ds, generator.generate(ds.policies[0]))
    assert "model ABACPolicies" in use_text
    assert "Natural_Language_Policy_Statement" in use_text


def test_prompt_and_json_parsing():
    messages = prompts.build_messages(EN[0], "en")
    assert any("schema" in m["content"].lower() for m in messages)
    parsed = parse_json_object('```json\n{"decision": "permit", "actions": []}\n```')
    assert parsed["decision"] == "permit"


def test_merge_rules_with_llm():
    ds = extract(["Civilian students can view rosters in the learning management system."])
    base = ds.policies[0]
    extra = extract(["dummy"]).policies[0]  # policy rỗng
    extra.subjects = []
    extra.actions = []
    extra.resource = None
    extra.environments = []
    merged = merge(base, extra)
    assert merged.subjects and merged.actions and merged.resource
    # LLM bổ sung chỗ trống
    empty = extract(["x"]).policies[0]
    empty.subjects, empty.actions, empty.resource, empty.environments = [], [], None, []
    patched = merge(empty, base)
    assert patched.subjects and patched.actions and patched.resource


class FakeClient:
    def extract(self, sentence, language="auto"):
        return {
            "decision": "deny",
            "modality": "cannot",
            "subjects": [{"role": "student", "entity_type": "user", "membership": "civilian"}],
            "actions": [{"verb": "register", "operation": "REGISTER"}],
            "resource": None,
            "environments": [{"id": "env_1", "env_type": "network", "namespace": "course_registration_system"}],
            "conditions": [{"text": "the system has not been activated", "kind": "condition"}],
        }


def test_enrich_with_fake_client():
    ds = extract([VI[1]])
    policy, state = enrich_with_llm(ds.policies[0], "hybrid", FakeClient())
    assert state == "ok"
    assert policy.decision == "deny"
    assert any(a.operation == "REGISTER" for a in policy.actions)


if __name__ == "__main__":
    test_extract_en()
    test_extract_vi()
    test_language_detection()
    test_generate_and_validate()
    test_writers()
    test_prompt_and_json_parsing()
    test_merge_rules_with_llm()
    test_enrich_with_fake_client()
    print("OK: 8 smoke tests passed")
