# -*- coding: utf-8 -*-
"""Demo Streamlit cho pipeline 3 mô-đun:  streamlit run app.py

Nhập câu chính sách (EN/VI) -> xem thành phần trích xuất (mô-đun 1), mô hình biểu diễn
USE (mô-đun 2), bất biến OCL theo mẫu IP (mô-đun 3); nếu có ABAC_USE_HOME thì kiểm
chứng bằng USE ngay trên giao diện.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import streamlit as st

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from abac.extraction import nlp                          # noqa: E402
from abac.extraction.pipeline import extract            # noqa: E402
from abac.modeling import puml, use_model               # noqa: E402
from abac.ocl import generator, use_runner, validator   # noqa: E402

EXAMPLES = {
    "id-11 (bài báo)": "Civilian students can view rosters in the learning management system "
                       "for courses that they are taking.",
    "id-46 (bài báo)": "A department chair can upload and download learning materials in the "
                       "learning management system for that department’s courses.",
    "id-88 (bài báo)": "Users who are not in the academic affairs office cannot number visiting "
                       "lecturer agreements in the visiting lecturer management system.",
    "Khung giờ": "Civilian students’ class schedules are only allowed in the academic "
                 "information system between 7:00 am and 5:25 pm.",
    "Thời lượng": "A retired visiting lecturer cannot teach more than 560 hours per year.",
    "Tiếng Việt": "Trưởng khoa có thể xem điểm của tất cả sinh viên dân sự trong hệ thống quản lý "
                  "học tập đối với các môn học của khoa đó.",
}


def run_pipeline(text: str) -> dict:
    sentences = [line.strip() for line in text.splitlines() if line.strip()]
    dataset = extract(sentences)
    model = use_model.build_model(dataset)
    pairs = {p.id: generator.generate_with_patterns(p) for p in dataset.policies}
    invariants = [inv for items in pairs.values() for _, inv in items]
    return {
        "dataset": dataset,
        "model": model,
        "pairs": pairs,
        "use": use_model.model_to_use(model, invariants),
        "soil": use_model.dataset_to_soil(dataset, model),
        "check": validator.check_all(invariants, model),
    }


def show_policy(p, pairs) -> None:
    with st.expander(f"Policy {p.id}: {p.sentence}", expanded=True):
        left, right = st.columns(2)
        with left:
            st.markdown("**Mô-đun 1 — thành phần chính sách**")
            st.json(p.to_dict(), expanded=False)
            roles = ", ".join(s.role or "(mọi người dùng)" for s in p.subjects) or "—"
            st.markdown(f"- Quyết định: `{p.decision}` · Chủ thể: `{roles}`\n"
                        f"- Hành động: `{', '.join(a.operation for a in p.actions) or '—'}`\n"
                        f"- Tài nguyên: `{p.resource.entity_type if p.resource else '—'}`\n"
                        f"- Điều kiện: `{', '.join(c.normalized or c.text for c in p.conditions) or '—'}`")
        with right:
            st.markdown("**Mô-đun 3 — bất biến OCL**")
            if not pairs:
                st.info("Câu không có hành động nên không sinh bất biến.")
            for ip, inv in pairs:
                st.caption(f"Mẫu IP: {ip}")
                st.code(inv, language="text")


def show_use_check(result: dict) -> None:
    if not use_runner.available():
        st.info("Đặt biến môi trường ABAC_USE_HOME (thư mục USE) và cài Java 21+ để kiểm chứng bằng USE.")
        return
    if not st.button("Kiểm chứng bằng USE"):
        return
    with tempfile.TemporaryDirectory() as tmp:
        spec, soil = os.path.join(tmp, "policies.use"), os.path.join(tmp, "policies.soil")
        with open(spec, "w", encoding="utf-8") as f:
            f.write(result["use"])
        with open(soil, "w", encoding="utf-8") as f:
            f.write(result["soil"])
        compiled = use_runner.compile_spec(spec)
        if not compiled.ok:
            st.error("USE báo lỗi đặc tả:\n" + "\n".join(compiled.errors[:20]))
            return
        state = use_runner.check_state(spec, soil)
        (st.success if state.ok else st.warning)(
            "use -c: OK · check: " + ("OK" if state.ok else "; ".join(state.errors[:10])))


def main() -> None:
    st.set_page_config(page_title="ABAC → OCL", layout="wide")
    st.title("Hình thức hoá chính sách ABAC theo ngữ cảnh")
    st.caption("NLPS (EN/VI) → thành phần chính sách → mô hình USE → bất biến OCL "
               f"· NLP: {'spaCy' if nlp.available() else 'regex'}")
    choice = st.selectbox("Câu mẫu", ["(tự nhập)"] + list(EXAMPLES))
    default = EXAMPLES.get(choice, EXAMPLES["id-11 (bài báo)"])
    text = st.text_area("Câu chính sách (mỗi dòng một câu)", value=default, height=120)
    if not text.strip():
        st.stop()
    result = run_pipeline(text)
    check = result["check"]
    st.markdown(f"**{len(result['dataset'].policies)} câu · {check['total']} bất biến · "
                f"{check['valid']} hợp lệ (cú pháp + ngữ nghĩa với mô hình)**")
    for p in result["dataset"].policies:
        show_policy(p, result["pairs"][p.id])
    st.subheader("Mô-đun 2 — mô hình biểu diễn")
    tab_use, tab_soil, tab_puml, tab_json = st.tabs(["policies.use", "policies.soil", "model.puml", "JSON"])
    tab_use.code(result["use"], language="text")
    tab_soil.code(result["soil"], language="text")
    tab_puml.code(puml.model_to_puml(result["model"]), language="text")
    tab_json.code(json.dumps(result["dataset"].to_dict(), ensure_ascii=False, indent=2), language="json")
    st.download_button("Tải policies.use", result["use"], file_name="policies.use")
    show_use_check(result)


main()
