#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Đo P/R/F1 của pipeline trên gold của nhóm tác giả (repo dataset [26] của bài báo).

    python scripts/eval_authors_gold.py --gold path/to/policy_dataset_gold.json \
        [--authors-machine path/to/policy_dataset.json] [--input data/vact_en.txt]

Gold và output máy của tác giả KHÔNG được đưa vào repo (repo gốc không có giấy phép);
tải từ https://github.com/nhatanh19-git/ABAC (thư mục result/VACT_final/).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from abac.evaluation.external_gold import FIELDS, gold_sets, policy_sets, score  # noqa: E402
from abac.extraction.pipeline import extract                                     # noqa: E402


def _load_policies(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["policies"]


def _print(title: str, result: dict) -> None:
    print(f"\n{title}")
    print(f"  {'trường':<12} {'P':>7} {'R':>7} {'F1':>7}   TP   FP   FN")
    for key in (*FIELDS, "micro_4", "micro_5"):
        r = result[key]
        print(f"  {key:<12} {r['precision']:>7.3f} {r['recall']:>7.3f} {r['f1']:>7.3f}"
              f" {r['tp']:>4} {r['fp']:>4} {r['fn']:>4}")


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser(description="Đánh giá trên gold của nhóm tác giả")
    ap.add_argument("--gold", required=True)
    ap.add_argument("--authors-machine", default=None, help="policy_dataset.json (output máy của tác giả)")
    ap.add_argument("--input", default=os.path.join(ROOT, "data", "vact_en.txt"))
    ap.add_argument("--json", default=None, help="ghi kết quả ra file JSON")
    args = ap.parse_args(argv)

    gold = {p["id"]: p for p in _load_policies(args.gold)}
    with open(args.input, encoding="utf-8") as f:
        texts = [line.strip() for line in f if line.strip()]
    ours = extract(texts)
    ids = sorted(gold)
    if len(ours.policies) != len(ids):
        print(f"[cảnh báo] pipeline: {len(ours.policies)} câu, gold: {len(ids)} câu")

    results = {"pipeline": score([(gold_sets(gold[pid]), policy_sets(p))
                                  for pid, p in zip(ids, ours.policies)])}
    _print("Pipeline này vs gold của tác giả", results["pipeline"])
    if args.authors_machine:
        machine = {p["id"]: p for p in _load_policies(args.authors_machine)}
        results["authors_machine"] = score([(gold_sets(gold[pid]), gold_sets(machine[pid]))
                                            for pid in ids if pid in machine])
        _print("Output máy của tác giả vs gold của tác giả (cùng phép ánh xạ)", results["authors_machine"])
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
