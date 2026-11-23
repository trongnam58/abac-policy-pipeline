#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Chạy toàn bộ pipeline (W1):

    python run_all.py --input data/vact_en_sample.txt --out out

Input : file text, mỗi dòng một câu chính sách (VI hoặc EN).
Output: out/policies.json, out/models/*.puml, out/models/policies.use,
        out/ocl/*.ocl, out/ocl/policies.ocl
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from abac.extraction.pipeline import extract_with_stats   # noqa: E402
from abac.modeling import puml, use_model             # noqa: E402
from abac.ocl import generator, validator             # noqa: E402
from abac.schema import load_dataset, save_dataset    # noqa: E402


def main(argv=None) -> int:
    try:  # console Windows mặc định cp932 không in được tiếng Việt
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Pipeline ABAC: NLPS -> JSON -> UML -> OCL")
    ap.add_argument("--input", required=True, help="file text, mỗi dòng một câu chính sách")
    ap.add_argument("--out", default="out", help="thư mục đầu ra (mặc định: out)")
    ap.add_argument("--llm-mode", choices=("off", "llm", "hybrid"), default="off",
                    help="off = chỉ rules; hybrid = rules + LLM; llm = chỉ LLM (cần ABAC_LLM_ENDPOINT)")
    ap.add_argument("--gold", default=None, help="file JSON gold cùng schema để đo P/R/F1")
    args = ap.parse_args(argv)

    with open(args.input, encoding="utf-8") as f:
        texts = [line.strip() for line in f if line.strip()]

    dataset, stats = extract_with_stats(texts, llm_mode=args.llm_mode)
    os.makedirs(os.path.join(args.out, "models"), exist_ok=True)
    os.makedirs(os.path.join(args.out, "ocl"), exist_ok=True)
    save_dataset(dataset, os.path.join(args.out, "policies.json"))

    invariants: list[str] = []
    for p in dataset.policies:
        with open(os.path.join(args.out, "models", f"policy_{p.id}.puml"), "w", encoding="utf-8") as f:
            f.write(puml.policy_to_puml(p))
        invs = generator.generate(p)
        invariants.extend(invs)
        with open(os.path.join(args.out, "ocl", f"policy_{p.id}.ocl"), "w", encoding="utf-8") as f:
            f.write("\n\n".join(invs) + ("\n" if invs else ""))

    with open(os.path.join(args.out, "models", "policies.use"), "w", encoding="utf-8") as f:
        f.write(use_model.dataset_to_use(dataset, invariants))
    with open(os.path.join(args.out, "ocl", "policies.ocl"), "w", encoding="utf-8") as f:
        f.write("\n\n".join(invariants) + "\n")

    check = validator.check_all(invariants)
    print(f"input     : {args.input} ({len(texts)} câu) — mode: {args.llm_mode}")
    if args.llm_mode != "off":
        print(f"llm       : {stats['llm_ok']} ok / {stats['llm_requests']} gọi, "
              f"{stats['llm_fallback']} fallback")
    print(f"policies  : {len(dataset.policies)} -> {os.path.join(args.out, 'policies.json')}")
    print(f"diagram   : {len(dataset.policies)} .puml -> {os.path.join(args.out, 'models')}")
    print(f"use model : {os.path.join(args.out, 'models', 'policies.use')}")
    print(f"ocl       : {check['valid']}/{check['total']} bất biến hợp lệ (kiểm tra nhẹ)")
    if check["issues"]:
        print(f"  lỗi     : {check['issues']}")
    if args.gold:
        from abac.evaluation.metrics import evaluate
        gold = load_dataset(args.gold)
        print(json.dumps(evaluate(dataset, gold), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
