#!/usr/bin/env python3
"""Content CLI.

  python3 scripts/quiz.py check --kg ../salesforce-knowledge-graph [--base-ref origin/main]
  python3 scripts/quiz.py build --kg ../salesforce-knowledge-graph [--out dist/questions.json]
  python3 scripts/quiz.py load  --table quiz-api-staging [--dataset dist/questions.json]
  python3 scripts/quiz.py coverage --kg ../salesforce-knowledge-graph
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quizapi import dataset  # noqa: E402


def _version() -> str:
    sha = os.environ.get("GITHUB_SHA")
    if not sha:
        try:
            sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                 text=True, check=True).stdout.strip()
        except subprocess.CalledProcessError:
            sha = "local"
    return sha[:12]


def cmd_check(args) -> int:
    files = dataset.load_question_files()
    kg = dataset.load_kg(Path(args.kg)) if args.kg else None
    base = dataset.load_base_question_files(args.base_ref) if args.base_ref else None
    report = dataset.validate(files, dataset.load_exams(), kg=kg, base=base)
    for w in report.warnings:
        print(f"warning: {w}")
    for e in report.errors:
        print(f"error: {e}")
    total = sum(len(d.get("questions", [])) for d in files.values())
    print(f"{len(files)} files, {total} questions, {len(report.errors)} errors, {len(report.warnings)} warnings")
    if kg is None:
        print("note: run with --kg to check articles and source ids against the knowledge graph")
    return 0 if report.ok else 1


def cmd_build(args) -> int:
    files = dataset.load_question_files()
    kg = dataset.load_kg(Path(args.kg))
    exams = dataset.load_exams()
    report = dataset.validate(files, exams, kg=kg)
    if not report.ok:
        for e in report.errors:
            print(f"error: {e}")
        return 1
    data = dataset.build(files, exams, kg, version=_version())
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out}: {data['meta']['questionCount']} published, {data['meta']['retiredCount']} retired")
    return 0


def cmd_load(args) -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from quizapi.api.repository import DynamoRepository

    data = json.loads(Path(args.dataset).read_text())
    written = DynamoRepository(args.table).replace_all(data)
    print(f"loaded {written} items into {args.table} (dataset {data['meta']['datasetVersion']})")
    return 0


def cmd_coverage(args) -> int:
    files = dataset.load_question_files()
    kg = dataset.load_kg(Path(args.kg))
    covered = {d["article"]: len(d["questions"]) for d in files.values()}
    missing = sorted(a for a in kg if a not in covered)
    print(f"{len(covered)}/{len(kg)} articles have questions")
    for a in missing:
        print(f"  no questions: {a} ({kg[a]['domain']})")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--kg")
    c.add_argument("--base-ref")
    b = sub.add_parser("build")
    b.add_argument("--kg", required=True)
    b.add_argument("--out", default=str(ROOT / "dist" / "questions.json"))
    lo = sub.add_parser("load")
    lo.add_argument("--table", required=True)
    lo.add_argument("--dataset", default=str(ROOT / "dist" / "questions.json"))
    cv = sub.add_parser("coverage")
    cv.add_argument("--kg", required=True)
    args = p.parse_args()
    return {"check": cmd_check, "build": cmd_build, "load": cmd_load, "coverage": cmd_coverage}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
