#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Chạy toàn bộ pipeline 3 mô-đun:

    python run_all.py --input data/vact_en.txt --out out

Input : file text, mỗi dòng một câu chính sách (VI hoặc EN).
Output: out/policies.json                 (mô-đun 1: thành phần chính sách)
        out/models/policies.use           (mô-đun 2: mô hình biểu diễn + bất biến)
        out/models/policies.soil          (thể hiện để USE `check`)
        out/models/model.puml             (sơ đồ lớp mô hình biểu diễn)
        out/models/policy_*.puml          (sơ đồ thể hiện từng chính sách)
        out/ocl/policy_*.ocl, policies.ocl (mô-đun 3: bất biến OCL)
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from abac.extraction import nlp                       # noqa: E402
from abac.extraction.pipeline import extract_with_stats   # noqa: E402
from abac.modeling import puml, use_model             # noqa: E402
from abac.ocl import generator, use_runner, validator  # noqa: E402
from abac.schema import PolicyDataset, load_dataset, save_dataset  # noqa: E402


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build_outputs(dataset: PolicyDataset, out: str) -> dict:
    """Mô-đun 2 + 3: ghi mô hình, thể hiện, sơ đồ và bất biến; trả thống kê."""
    models_dir, ocl_dir = os.path.join(out, "models"), os.path.join(out, "ocl")
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(ocl_dir, exist_ok=True)
    model = use_model.build_model(dataset)
    invariants: list[str] = []
    pattern_counts: Counter = Counter()
    for p in dataset.policies:
        _write(os.path.join(models_dir, f"policy_{p.id}.puml"), puml.policy_to_puml(p))
        pairs = generator.generate_with_patterns(p)
        pattern_counts.update(ip for ip, _ in pairs)
        invs = [inv for _, inv in pairs]
        invariants.extend(invs)
        _write(os.path.join(ocl_dir, f"policy_{p.id}.ocl"), "\n\n".join(invs) + ("\n" if invs else ""))
    paths = {
        "use": os.path.join(models_dir, "policies.use"),
        "soil": os.path.join(models_dir, "policies.soil"),
    }
    _write(paths["use"], use_model.model_to_use(model, invariants))
    _write(paths["soil"], use_model.dataset_to_soil(dataset, model))
    _write(os.path.join(models_dir, "model.puml"), puml.model_to_puml(model))
    _write(os.path.join(ocl_dir, "policies.ocl"), "\n\n".join(invariants) + "\n")
    return {"model": model, "invariants": invariants, "patterns": pattern_counts, "paths": paths,
            "check": validator.check_all(invariants, model)}


def run_use_check(paths: dict) -> int:
    if not use_runner.available():
        print("use check : bỏ qua — đặt ABAC_USE_HOME tới thư mục USE và cài Java 21+")
        return 1
    compiled = use_runner.compile_spec(paths["use"])
    print(f"use -c    : {'OK' if compiled.ok else 'LỖI'}")
    for err in compiled.errors[:20]:
        print(f"  {err}")
    if not compiled.ok:
        return 1
    state = use_runner.check_state(paths["use"], paths["soil"])
    print(f"use check : {'OK' if state.ok else 'có lỗi/vi phạm'} (trạng thái mẫu từ policies.soil)")
    for err in state.errors[:20]:
        print(f"  {err}")
    return 0


def run_semantic_check(dataset: PolicyDataset, model, out: str) -> int:
    """Kiểm thử ngữ nghĩa từng policy bằng USE: trạng thái tuân thủ phải 0 failures,
    trạng thái vi phạm phải làm mọi bất biến của policy FAILED.

    Mỗi nhóm chủ thể (vd. "academic coordinator and chair" -> 2 nhóm) được kiểm trên một
    trạng thái riêng chỉ có người dùng của nhóm đó: mẫu IP dùng User.allInstances()->forAll,
    nên trạng thái có người dùng mang vai trò khác làm vế trái sai (bất biến đúng hiển nhiên).
    """
    if not use_runner.available():
        print("semantic  : bỏ qua — đặt ABAC_USE_HOME tới thư mục USE và cài Java 21+")
        return 1
    sem_dir = os.path.join(out, "semantic")
    os.makedirs(sem_dir, exist_ok=True)
    report, failed = [], []
    for p in dataset.policies:
        groups = generator.subject_groups(p, generator.select_ip(p))
        for k, group in enumerate(groups, 1):
            q = dataclasses.replace(p, subjects=list(group) or list(p.subjects))
            invs = generator.generate(q)
            if not invs:
                continue
            stem = f"policy_{p.id}" + (f"_s{k}" if len(groups) > 1 else "")
            use_path = os.path.join(sem_dir, f"{stem}.use")
            soil_path = os.path.join(sem_dir, f"{stem}.soil")
            _write(use_path, use_model.model_to_use(model, invs))
            _write(soil_path, use_model.semantic_check_soil(q, model))
            r = use_runner.semantic_check(use_path, soil_path)
            report.append({"id": p.id, "case": stem, "ok": r.ok, "invariants": r.invariants,
                           "compliant_failures": r.compliant_failures,
                           "violating_failures": r.violating_failures})
            if not r.ok:
                failed.append((stem, r))
    _write(os.path.join(sem_dir, "report.json"), json.dumps(report, ensure_ascii=False, indent=2))
    policies = {row["id"] for row in report}
    bad = {row["id"] for row in report if not row["ok"]}
    print(f"semantic  : {len(policies) - len(bad)}/{len(policies)} policy đạt "
          f"({len(report)} trường hợp; tuân thủ: 0 failures; vi phạm: mọi bất biến FAILED) -> {sem_dir}")
    for stem, r in failed[:20]:
        print(f"  {stem}: tuân thủ {r.compliant_failures} failures, "
              f"vi phạm {r.violating_failures}/{r.invariants} FAILED {r.detail[-300:]!r}")
    return 0 if not failed else 1


def main(argv=None) -> int:
    try:  # console Windows mặc định không in được tiếng Việt
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser(description="Pipeline ABAC: NLPS -> JSON -> UML/USE -> OCL")
    ap.add_argument("--input", required=True, help="file text, mỗi dòng một câu chính sách")
    ap.add_argument("--out", default="out", help="thư mục đầu ra (mặc định: out)")
    ap.add_argument("--llm-mode", choices=("off", "llm", "hybrid"), default="off",
                    help="off = chỉ rules; hybrid = rules + LLM; llm = chỉ LLM (cần ABAC_LLM_ENDPOINT)")
    ap.add_argument("--gold", default=None, help="file JSON gold cùng schema để đo P/R/F1")
    ap.add_argument("--use-check", action="store_true",
                    help="kiểm chứng policies.use/.soil bằng USE (cần ABAC_USE_HOME)")
    ap.add_argument("--semantic-check", action="store_true",
                    help="kiểm thử ngữ nghĩa từng policy bằng USE (trạng thái tuân thủ / vi phạm)")
    args = ap.parse_args(argv)

    with open(args.input, encoding="utf-8") as f:
        texts = [line.strip() for line in f if line.strip()]

    dataset, stats = extract_with_stats(texts, llm_mode=args.llm_mode)
    os.makedirs(args.out, exist_ok=True)
    save_dataset(dataset, os.path.join(args.out, "policies.json"))
    result = build_outputs(dataset, args.out)

    check = result["check"]
    print(f"input     : {args.input} ({len(texts)} câu) — mode: {args.llm_mode}, "
          f"NLP: {'spaCy' if nlp.available() else 'regex (chưa cài spaCy)'}")
    if args.llm_mode != "off":
        print(f"llm       : {stats['llm_ok']} ok / {stats['llm_requests']} gọi, "
              f"{stats['llm_fallback']} fallback")
    print(f"policies  : {len(dataset.policies)} -> {os.path.join(args.out, 'policies.json')}")
    print(f"use model : {result['paths']['use']} (+ policies.soil, model.puml)")
    print(f"ocl       : {check['total']} bất biến, {check['valid']} hợp lệ (cú pháp + ngữ nghĩa với mô hình)")
    print(f"mẫu IP    : {dict(result['patterns'])}")
    if check["issues"]:
        print(f"  lỗi     : {check['issues']}")
    if args.gold:
        from abac.evaluation.metrics import evaluate
        print(json.dumps(evaluate(dataset, load_dataset(args.gold)), ensure_ascii=False, indent=2))
    status = 0
    if args.use_check:
        status |= run_use_check(result["paths"])
    if args.semantic_check:
        status |= run_semantic_check(dataset, result["model"], args.out)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
