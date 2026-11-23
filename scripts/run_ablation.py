#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Ablation 3 cấu hình trích xuất: rules / hybrid / llm.

    python scripts/run_ablation.py --input data/vact_en_sample.txt --gold data/gold_sample.json

Nếu chưa cấu hình ABAC_LLM_ENDPOINT, hai cấu hình có LLM sẽ bị đánh dấu "skipped"
và summary.json ghi rõ lý do — số liệu ablation thật chỉ chạy khi có endpoint.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from abac.evaluation.metrics import evaluate            # noqa: E402
from abac.extraction.pipeline import extract_with_stats  # noqa: E402
from abac.schema import load_dataset, save_dataset      # noqa: E402

COMPONENTS = ("subject_role", "action", "resource", "environment")


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Ablation rules / hybrid / llm")
    ap.add_argument("--input", default=os.path.join(ROOT, "data", "vact_en_sample.txt"))
    ap.add_argument("--gold", default=os.path.join(ROOT, "data", "gold_sample.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "ablation"))
    args = ap.parse_args(argv)

    with open(args.input, encoding="utf-8") as f:
        texts = [line.strip() for line in f if line.strip()]
    gold = load_dataset(args.gold) if args.gold else None
    os.makedirs(args.out, exist_ok=True)

    summary: dict = {}
    for mode in ("rules", "hybrid", "llm"):
        if mode != "rules" and not os.environ.get("ABAC_LLM_ENDPOINT"):
            summary[mode] = {"status": "skipped", "reason": "chưa cấu hình ABAC_LLM_ENDPOINT"}
            print(f"{mode:7s} || bỏ qua (chưa cấu hình ABAC_LLM_ENDPOINT)")
            continue
        dataset, stats = extract_with_stats(
            texts, llm_mode="off" if mode == "rules" else mode)
        save_dataset(dataset, os.path.join(args.out, f"{mode}.json"))
        metrics = evaluate(dataset, gold) if gold else None
        summary[mode] = {"status": "done", "stats": stats, "metrics": metrics}
        line = f"{mode:7s} || policies {stats['policies']:3d}"
        if metrics:
            line += f" | micro F1 {metrics['micro']['f1']:.3f}"
            for comp in COMPONENTS:
                line += f" | {comp} {metrics[comp]['f1']:.3f}"
        print(line)

    path = os.path.join(args.out, "summary.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"summary  : {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
