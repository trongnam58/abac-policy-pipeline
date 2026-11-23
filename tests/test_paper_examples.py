# -*- coding: utf-8 -*-
"""Kiểm tra pipeline bám theo bài báo: ví dụ id-11, id-46, id-88 (mục 4.2), các phép
biến đổi của mô-đun 2 (mục 3.1) và 3 mẫu IP (Fig. 5–7). Chạy: pytest
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from abac.extraction import nlp                         # noqa: E402
from abac.extraction.common import detect_duration, normalize, ocl_operator  # noqa: E402
from abac.extraction.pipeline import extract           # noqa: E402
from abac.modeling import puml, use_model              # noqa: E402
from abac.ocl import generator, use_runner, validator  # noqa: E402
from abac.schema import PolicyDataset, load_dataset, save_dataset  # noqa: E402

ID11 = "Civilian students can view rosters in the learning management system for courses that they are taking."
ID46 = ("A department chair can upload and download learning materials in the learning management "
        "system for that department’s courses.")
ID88 = ("Users who are not in the academic affairs office cannot number visiting lecturer "
        "agreements in the visiting lecturer management system.")
TIME = "Civilian students’ class schedules are only allowed in the academic information system between 7:00 am and 5:25 pm."
HOURS = "A retired visiting lecturer cannot teach more than 560 hours per year."
OR_OFFICE = ("Users in the academic affairs or finance office can view the details of visiting "
             "lecturer agreements in the visiting lecturer management system.")


@pytest.fixture(scope="module")
def paper():
    return extract([ID11, ID46, ID88])


def _flat(text: str) -> str:
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Mô-đun 1
# ---------------------------------------------------------------------------

def test_id11_extracts_contextual_condition(paper):
    p = paper.policies[0]
    assert p.subjects[0].role == "student" and p.subjects[0].membership == "civilian"
    assert p.resource.entity_type == "roster"
    assert [c.normalized for c in p.conditions] == ["for_courses_that_they_are_taking"]


def test_id46_resource_level_and_chair_position(paper):
    p = paper.policies[1]
    assert [a.operation for a in p.actions] == ["UPLOAD", "DOWNLOAD"]
    assert p.subjects[0].position == "chair"
    assert p.resource.attributes == {"level": "department"}
    assert p.conditions[0].normalized == "for_that_department"


def test_id88_generic_users_and_negated_scope(paper):
    p = paper.policies[2]
    assert p.decision == "deny"
    assert [s.role for s in p.subjects] == [""]
    assert p.conditions[0].normalized == "not_in_the_academic_affairs_office"


def test_temporal_window_and_implicit_access():
    p = extract([TIME]).policies[0]
    assert [a.operation for a in p.actions] == ["READ"]
    window = [e for e in p.environments if e.env_type == "temporal"][0]
    assert (window.time_from, window.time_to) == ("07:00", "17:25")


def test_duration_constraint_with_operator():
    p = extract([HOURS]).policies[0]
    d = [e for e in p.environments if e.env_type == "duration"][0]
    assert (d.operator, d.value, d.unit, d.period) == (">", 560.0, "hours", "year")


@pytest.mark.parametrize("phrase,op", [
    ("more than", ">"), ("at most", "<="), ("at least", ">="), ("less than", "<"),
    ("no more than", "<="), ("exactly", "="), ("vượt quá", ">"),
])
def test_determine_ocl_operator(phrase, op):
    assert ocl_operator(phrase) == op


def test_logical_operator_or_for_alternative_offices():
    p = extract([OR_OFFICE]).policies[0]
    assert p.logical_operator == "or"
    assert {s.position for s in p.subjects} == {"academic_affairs_office", "finance_office"}


def test_participle_modifier_is_not_action():
    p = extract(["Civilian students can view the status of registered courses in the course registration system."]).policies[0]
    assert [a.operation for a in p.actions] == ["READ"]


def test_vietnamese_parity_for_duration_and_scope():
    vi = extract(["Giảng viên thỉnh giảng đã nghỉ hưu không thể giảng dạy quá 560 giờ mỗi năm.",
                  "Trưởng khoa có thể xem điểm của tất cả sinh viên dân sự trong hệ thống quản lý "
                  "học tập đối với các môn học của khoa đó."]).policies
    assert vi[0].decision == "deny" and vi[0].environments[0].operator == ">"
    assert vi[1].resource.attributes == {"level": "department"}
    assert vi[1].subjects[0].position == "chair"


def test_normalize():
    assert normalize("for that department’s courses") == "for_that_department"
    assert normalize("only for that department") == "for_that_department"
    assert detect_duration("no limits here") is None


def test_regex_fallback_without_spacy(monkeypatch):
    monkeypatch.setenv("ABAC_DISABLE_SPACY", "1")
    nlp.reset()
    try:
        assert nlp.annotate("anything") is None
        p = extract([ID46]).policies[0]
        assert [a.operation for a in p.actions] == ["UPLOAD", "DOWNLOAD"]
    finally:
        monkeypatch.delenv("ABAC_DISABLE_SPACY")
        nlp.reset()


# ---------------------------------------------------------------------------
# Mô-đun 2
# ---------------------------------------------------------------------------

def test_module_two_transformations(paper):
    model = use_model.build_model(paper)
    assert "SubjectType" not in model.classes and "ObjectType" not in model.classes
    assert {"Roster", "Learning_Material", "Visiting_Lecturer_Agreement"} <= set(model.classes)
    assert ("level", "String") in model.classes["Learning_Material"]
    assert model.enums["Role"] == ["student", "department_chair"]
    assert model.enums["Network"] == ["learning_management_system", "visiting_lecturer_management_system"]
    assert {"READexecuted", "UPLOADexecuted", "DOWNLOADexecuted", "NUMBERexecuted"} <= model.attribute_names("Action")
    assert all(n != "otherAttributes" for attrs in model.classes.values() for n, _ in attrs)
    assert "am" in model.enums["TimeUnit"]


def test_use_spec_structure(paper):
    invs = [i for p in paper.policies for i in generator.generate(p)]
    text = use_model.dataset_to_use(paper, invs)
    assert text.index("enum Role") < text.index("class User")
    assert "associationclass Context between" in text
    assert "association Object_Roster between" in text
    assert "\nconstraints\n" in text and "!create" not in text


def test_soil_instances(paper):
    soil = use_model.dataset_to_soil(paper)
    assert "!create c1_1_1 : Context between (a1_1, e1_1)" in soil
    assert "!set r2.level := 'department'" in soil
    assert "!insert (o1, r1) into Object_Roster" in soil
    assert soil.rstrip().endswith("check")


def test_class_diagram(paper):
    text = puml.model_to_puml(use_model.build_model(paper))
    assert text.startswith("@startuml") and "(Action, Environment) .. Context" in text


# ---------------------------------------------------------------------------
# Mô-đun 3
# ---------------------------------------------------------------------------

def test_id11_uses_contextual_user(paper):
    (ip, inv), = generator.generate_with_patterns(paper.policies[0])
    assert ip == "ContextualUser"
    assert _flat(inv) == _flat("""context Context inv policy_1_1:
      network=#learning_management_system
      and consideredContext='for_courses_that_they_are_taking'
      and User.allInstances()->forAll(u | u.roleActivated=#student
            and u.typeMembership='civilian'
            and u.subject.actions.objects.roster->notEmpty())
      implies environments.actions->exists(namesAction='READ')
            and actions.READexecuted=true""")


def test_id46_uses_contextual_user_object_type(paper):
    pairs = generator.generate_with_patterns(paper.policies[1])
    assert [ip for ip, _ in pairs] == ["ContextualUserObjectType"] * 2
    assert "Learning_Material.allInstances()->forAll(ot | ot.level='department')" in pairs[0][1]
    assert "u.position='chair'" in pairs[0][1]
    assert pairs[1][1].endswith("actions.DOWNLOADexecuted=true")


def test_id88_uses_contextual_user_restricted(paper):
    (ip, inv), = generator.generate_with_patterns(paper.policies[2])
    assert ip == "ContextualUserRestricted"
    assert "roleActivated" not in inv
    assert "consideredContext='not_in_the_academic_affairs_office'" in inv
    assert inv.endswith("actions.NUMBERexecuted=false")


def test_temporal_and_duration_invariants():
    ds = extract([TIME, HOURS])
    window, hours = (generator.generate(p)[0] for p in ds.policies)
    assert "timeInPoint >= '07:00'" in window and "timeInPoint <= '17:25'" in window
    assert "duration > 560" in hours and "durationUnit=#hours" in hours
    assert hours.endswith("TEACHexecuted=false")


def test_or_alternatives_in_single_invariant():
    invs = generator.generate(extract([OR_OFFICE]).policies[0])
    assert len(invs) == 1 and " or " in invs[0]


def test_semantic_validator_on_full_dataset():
    with open(os.path.join(ROOT, "data", "vact_en.txt"), encoding="utf-8") as f:
        ds = extract([line for line in f if line.strip()])
    assert len(ds.policies) == 100
    model = use_model.build_model(ds)
    invs = [i for p in ds.policies for i in generator.generate(p)]
    check = validator.check_all(invs, model)
    assert check["valid"] == check["total"] > 100, check["issues"]


def test_semantic_validator_detects_unknown_names(paper):
    model = use_model.build_model(paper)
    bad = ("context Context inv x:\n  network=#nowhere and colour='red'\n"
           "  and User.allInstances()->forAll(u | u.age=3 and u.subject.actions.objects.car->notEmpty())\n"
           "  implies environments.actions->exists(namesAction='FLY')\n        and actions.FLYexecuted=true")
    issues = " | ".join(validator.validate(bad, model))
    for needle in ("#nowhere", "colour", "age", "car", "FLYexecuted"):
        assert needle in issues


def test_schema_roundtrip(tmp_path, paper):
    path = tmp_path / "p.json"
    save_dataset(paper, str(path))
    again = load_dataset(str(path))
    assert again.to_dict() == paper.to_dict()
    assert isinstance(again, PolicyDataset)


def test_use_runner_reports_missing_configuration(monkeypatch):
    monkeypatch.delenv("ABAC_USE_HOME", raising=False)
    assert use_runner.available() is False
    with pytest.raises(RuntimeError):
        use_runner.compile_spec("x.use")


@pytest.mark.skipif(not use_runner.available(), reason="cần ABAC_USE_HOME + Java để chạy USE")
def test_use_compiles_generated_model(tmp_path, paper):
    invs = [i for p in paper.policies for i in generator.generate(p)]
    spec = tmp_path / "policies.use"
    spec.write_text(use_model.dataset_to_use(paper, invs), encoding="utf-8")
    result = use_runner.compile_spec(str(spec))
    assert result.ok, result.output


def test_metrics_against_gold_sample():
    from abac.evaluation.metrics import evaluate
    with open(os.path.join(ROOT, "data", "vact_en_sample.txt"), encoding="utf-8") as f:
        pred = extract([line for line in f if line.strip()])
    result = evaluate(pred, load_dataset(os.path.join(ROOT, "data", "gold_sample.json")))
    assert result["policies"] == 20
    assert result["subject_role"]["f1"] == 1.0 and result["environment"]["f1"] == 1.0
    assert result["micro"]["f1"] >= 0.95


# ---------------------------------------------------------------------------
# Hồi quy theo code review
# ---------------------------------------------------------------------------

def test_start_time_without_meridiem_is_not_shifted_past_end():
    p = extract(["Lecturers can view rosters in the learning management system for that "
                 "department’s courses between 8:00 and 5:00 pm."]).policies[0]
    window = [e for e in p.environments if e.env_type == "temporal"][0]
    assert (window.time_from, window.time_to) == ("08:00", "17:00")
    assert all("between" not in (c.normalized or "") for c in p.conditions)


def test_from_dict_sanitizes_untrusted_duration():
    from abac.schema import Policy
    p = Policy.from_dict({"id": 1, "sentence": "x", "actions": [{"verb": "teach", "operation": "TEACH"}],
                          "environments": [{"env_type": "duration", "operator": "more than",
                                            "value": "560", "unit": "hour"}]})
    env = p.environments[0]
    assert (env.operator, env.value, env.unit) == (None, None, None)
    assert "#None" not in generator.generate(p)[0]
    ok = Policy.from_dict({"environments": [{"operator": ">", "value": "560", "unit": "hours"}]})
    assert (ok.environments[0].operator, ok.environments[0].value) == (">", 560.0)


def test_ident_is_ascii_and_avoids_reserved_words():
    assert use_model.ident("giảng_viên đồ án") == "giang_vien_do_an"
    assert use_model.ident("end") == "v_end" and use_model.ident("1st") == "v_1st"
    assert use_model.attribute_ident("id") == "attr_id"


def test_check_state_marks_failed_invariants(monkeypatch):
    fake = use_runner.UseResult(ok=True, command=[], output="checking invariant (1) `Context::p': FAILED.\n", errors=[])
    monkeypatch.setattr(use_runner, "_run", lambda *a, **k: fake)
    result = use_runner.check_state("m.use", "s.soil")
    assert result.ok is False and result.errors


# ---------------------------------------------------------------------------
# Đánh giá với gold theo schema của nhóm tác giả (dữ liệu tổng hợp)
# ---------------------------------------------------------------------------

def test_external_gold_mapping_and_score(paper):
    from abac.evaluation.external_gold import gold_sets, head_noun, policy_sets, score
    gold_main = {
        "id": 1,
        "subjects": [{"role": "student"}],
        "actions": [{"operation": "READ"}],
        "resource": {"label": "roster"},
        "environments": [{"env_type": "system", "systems": [
            {"namespace": "environment.device.device_type:learning_management_system"}]}],
        "context": [{"trigger_phrase": "for courses that they are taking"}],
    }
    gold_alt = {"id": 2, "subject": ["class schedules"], "actions": ["allow"], "object": ["information system"],
                "environments": [{"env_type": "temporal", "phrase": "7:00 am and 5:25 pm"}], "context": []}
    g1, g2 = gold_sets(gold_main), gold_sets(gold_alt)
    assert g1["environment"] == {"learning_management_system"} and g1["object"] == {"roster"}
    assert g2["action"] == {"ALLOW"} and g2["environment"] == {"temporal"} and g2["object"] == {"system"}
    assert head_noun("multiple-choice_exams") == "exam" and head_noun("status") == "status"
    result = score([(g1, policy_sets(paper.policies[0]))])
    assert result["micro_5"]["f1"] == 1.0


# ---------------------------------------------------------------------------
# Ràng buộc đếm, tên vai trò ngắn, trạng thái chứng cứ cho USE
# ---------------------------------------------------------------------------

COUNT = ("A civilian student can register for at most one graduation project topic in the "
         "learning management system from the list of suggested topics uploaded by an instructor.")


def test_cardinality_constraint_uses_extension_pattern():
    p = extract([COUNT]).policies[0]
    assert (p.resource.count_operator, p.resource.count) == ("<=", 1)
    (ip, inv), = generator.generate_with_patterns(p)
    assert ip == "ContextualUserCardinality"
    assert "objects.graduation_project_topic->size() > 1" in inv
    assert inv.endswith("REGISTERexecuted=false")


def test_id88_uses_short_role_name_like_the_paper(paper):
    inv = generator.generate(paper.policies[2])[0]
    assert "u.subject.actions.objects.agreement->notEmpty()" in inv


def test_within_the_year_is_temporal():
    p = extract(["The finance office can approve visiting lecturer classes in the visiting lecturer "
                 "management system only if the total teaching hours of a visiting lecturer within "
                 "the year do not exceed the prescribed limit."]).policies[0]
    assert any(e.env_type == "temporal" and e.period == "year" for e in p.environments)
    assert "typeConstraintActivated=#TemporalConstraint" in generator.generate(p)[0]


def test_operator_helpers():
    from abac.ocl.patterns import negate, witness_number
    assert [negate(op) for op in ("<=", ">", "=")] == [">", "<=", "<>"]
    assert witness_number(">", 560) == 561 and witness_number("<=", 3) == 3


def test_semantic_soil_has_compliant_and_violating_states(paper):
    model = use_model.build_model(paper)
    soil = use_model.semantic_check_soil(paper.policies[0], model)
    compliant, violating = soil.split("reset")
    assert "READexecuted := true" in compliant and "READexecuted := false" in violating
    assert soil.count("check") == 2


def test_cardinality_witness_creates_enough_resources():
    p = extract([COUNT]).policies[0]
    soil = "\n".join(use_model.policy_to_soil(p, use_model.build_model(extract([COUNT]))))
    assert soil.count(": Graduation_Project_Topic") == 2


@pytest.mark.skipif(not use_runner.available(), reason="cần ABAC_USE_HOME + Java để chạy USE")
@pytest.mark.parametrize("sentence", [ID11, ID46, ID88, COUNT, HOURS, TIME])
def test_use_semantic_check_distinguishes_compliance(tmp_path, sentence):
    ds = extract([sentence])
    p, model = ds.policies[0], use_model.build_model(ds)
    spec, soil = tmp_path / "p.use", tmp_path / "p.soil"
    spec.write_text(use_model.model_to_use(model, generator.generate(p)), encoding="utf-8")
    soil.write_text(use_model.semantic_check_soil(p, model), encoding="utf-8")
    r = use_runner.semantic_check(str(spec), str(soil))
    assert r.ok, (r.compliant_failures, r.violating_failures, r.detail)


def test_vietnamese_translation_parity_with_english():
    """data/vact_vi.txt (bản dịch nháp, khớp từng dòng) phải trích xuất tương đương bản EN."""
    from abac.evaluation.metrics import evaluate

    def read(name):
        with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    en, vi = extract(read("vact_en.txt")), extract(read("vact_vi.txt"))
    assert len(vi.policies) == len(en.policies) == 100
    result = evaluate(vi, en)
    assert result["micro"]["f1"] >= 0.95, result
    assert all(a.decision == b.decision for a, b in zip(en.policies, vi.policies))
