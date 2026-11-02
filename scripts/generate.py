#!/usr/bin/env python3
"""Draft questions for knowledge-graph articles that don't have any yet.

  ANTHROPIC_API_KEY=... python3 scripts/generate.py --kg ../salesforce-knowledge-graph --articles 3

Drafts are written to questions/<domain>/<slug>.yaml and validated. They are never published directly:
the generate workflow opens a pull request, and a human reviewer checks every question against the cited
article before merging. Merging the PR is the publish step.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quizapi import dataset  # noqa: E402

MODEL = os.environ.get("QUIZ_MODEL", "claude-sonnet-5-5")

SYSTEM = """You write original Salesforce practice questions for an open, CC BY 4.0 question bank.

Rules:
- Ground every question ONLY in the article you are given. Never use outside knowledge for the answer.
- Never reproduce or paraphrase real Salesforce certification exam questions. Write original scenarios.
- Each question tests one idea that matters in practice: a behavior, limit, trade-off or best practice.
- Prefer short scenarios ("An admin needs to...") over bare recall, and mix difficulties.
- 4 options (a-d) for single-answer questions; 5 options (a-e) for "Choose 2" multiple-answer questions,
  and the stem must say "(Choose 2.)". Distractors must be plausible and clearly wrong per the article.
- Vary the position of the correct answer.
- The explanation says why the answer is right and, briefly, why the tempting distractor is wrong,
  citing only facts in the article. 40-120 words.
- `sources` lists the article source ids (s1, s2, ...) whose cited paragraphs support the answer.
- `exams` uses only slugs from the provided list, and only where the topic genuinely fits."""

TOOL = {
    "name": "submit_questions",
    "description": "Submit the drafted questions.",
    "input_schema": {
        "type": "object",
        "required": ["questions"],
        "properties": {
            "questions": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["type", "difficulty", "stem", "options", "answer", "explanation", "sources", "exams"],
                    "properties": {
                        "type": {"enum": ["single", "multiple"]},
                        "difficulty": {"enum": ["easy", "medium", "hard"]},
                        "stem": {"type": "string"},
                        "options": {"type": "array", "items": {
                            "type": "object", "required": ["id", "text"],
                            "properties": {"id": {"type": "string"}, "text": {"type": "string"}}}},
                        "answer": {"type": "array", "items": {"type": "string"}},
                        "explanation": {"type": "string"},
                        "sources": {"type": "array", "items": {"type": "string"}},
                        "exams": {"type": "array", "items": {"type": "string"}},
                    },
                },
            }
        },
    },
}


def pick_articles(kg: dict, existing: set[str], n: int) -> list[dict]:
    candidates = [a for a in kg.values() if a["id"] not in existing and a.get("status") != "retired"
                  and a.get("type") != "Certification"]
    # Articles mapped to a certification first, then oldest first, so coverage grows predictably.
    candidates.sort(key=lambda a: (
        not any(r.get("predicate") == "coveredBy" for r in a.get("relations") or []),
        str(a.get("created")), a["id"]))
    return candidates[:n]


def draft(client, article: dict, kg_root: Path, exams: dict, count: int) -> list[dict]:
    text = (kg_root / article["_file"]).read_text()
    prompt = (
        f"Write {count} questions for this article. Exam slugs you may use:\n"
        f"{json.dumps({k: v['name'] for k, v in exams.items()})}\n\n<article>\n{text}\n</article>"
    )
    msg = client.messages.create(
        model=MODEL, max_tokens=4000, system=SYSTEM, tools=[TOOL],
        tool_choice={"type": "tool", "name": "submit_questions"},
        messages=[{"role": "user", "content": prompt}],
    )
    block = next(b for b in msg.content if b.type == "tool_use")
    return block.input["questions"]


def to_file(article: dict, drafted: list[dict], today: str) -> dict:
    slug = article["id"].split(":", 1)[1]
    questions = []
    for i, q in enumerate(drafted, start=1):
        questions.append({
            "id": f"{slug}-{i:03d}", "status": "published", "type": q["type"], "difficulty": q["difficulty"],
            "stem": q["stem"].strip(),
            "options": [{"id": o["id"].strip().lower(), "text": o["text"].strip()} for o in q["options"]],
            "answer": sorted(a.strip().lower() for a in q["answer"]),
            "explanation": q["explanation"].strip(),
            "exams": q.get("exams", []),
            "sources": q["sources"], "created": today, "updated": today,
        })
    return {"article": article["id"], "questions": questions}


class _Dumper(yaml.SafeDumper):
    pass


def _str(dumper, value):
    style = ">" if len(value) > 100 else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--kg", required=True)
    p.add_argument("--articles", type=int, default=3)
    p.add_argument("--per-article", type=int, default=3)
    args = p.parse_args()

    import anthropic

    client = anthropic.Anthropic()
    kg_root = Path(args.kg)
    kg = dataset.load_kg(kg_root)
    exams = dataset.load_exams()
    existing = {d["article"] for d in dataset.load_question_files().values()}
    today = dt.date.today().isoformat()
    written = []

    for article in pick_articles(kg, existing, args.articles):
        doc = to_file(article, draft(client, article, kg_root, exams, args.per_article), today)
        rel = f"questions/{article['domain']}/{article['id'].split(':', 1)[1]}.yaml"
        report = dataset.validate({rel: doc}, exams, kg=kg)
        if not report.ok:
            print(f"skipped {article['id']}: draft failed validation")
            for e in report.errors:
                print(f"  {e}")
            continue
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.dump(doc, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=110))
        written.append(rel)
        print(f"wrote {rel} ({len(doc['questions'])} questions)")

    summary = ROOT / "dist" / "generated.txt"
    summary.parent.mkdir(exist_ok=True)
    summary.write_text("\n".join(written) + ("\n" if written else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
