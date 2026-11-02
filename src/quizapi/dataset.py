"""Validate question files and compile them into the dataset the API serves.

Build-time only: depends on PyYAML and jsonschema, which the Lambda never imports.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
import yaml

from . import API_VERSION, ATTRIBUTION, CONTENT_LICENSE

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_DIR = "questions"
KG_SITE = "https://john1hsu.github.io/salesforce-knowledge-graph/articles/{slug}.html"
KG_REPO = "https://github.com/john1hsu/salesforce-knowledge-graph"


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")

    @property
    def ok(self) -> bool:
        return not self.errors


def _yaml_load(text: str):
    # Keep dates as strings so they round-trip into JSON unchanged.
    class Loader(yaml.SafeLoader):
        pass

    Loader.yaml_implicit_resolvers = {
        k: [r for r in v if r[0] != "tag:yaml.org,2002:timestamp"]
        for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }
    return yaml.load(text, Loader=Loader)


def load_exams(root: Path = ROOT) -> dict:
    return _yaml_load((root / "exams.yaml").read_text())


def load_question_files(root: Path = ROOT) -> dict[str, dict]:
    """Return {relative path: parsed file}."""
    out = {}
    for path in sorted((root / QUESTIONS_DIR).rglob("*.yaml")):
        out[str(path.relative_to(root))] = _yaml_load(path.read_text())
    return out


def load_base_question_files(ref: str, root: Path = ROOT) -> dict[str, dict]:
    """Question files as they exist at a git ref (for the permanent-id check)."""
    try:
        names = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", ref, QUESTIONS_DIR],
            cwd=root, check=True, capture_output=True, text=True,
        ).stdout.split()
    except subprocess.CalledProcessError:
        return {}
    out = {}
    for name in names:
        if name.endswith(".yaml"):
            text = subprocess.run(
                ["git", "show", f"{ref}:{name}"], cwd=root, check=True, capture_output=True, text=True
            ).stdout
            out[name] = _yaml_load(text)
    return out


def load_kg(kg_root: Path) -> dict[str, dict]:
    """Article frontmatter keyed by node id, read from a salesforce-knowledge-graph checkout."""
    articles = {}
    for path in (kg_root / "articles").rglob("*.md"):
        text = path.read_text()
        if not text.startswith("---"):
            continue
        fm = _yaml_load(text.split("---", 2)[1])
        if fm and "id" in fm:
            fm["_file"] = str(path.relative_to(kg_root))
            articles[fm["id"]] = fm
    return articles


def _schema() -> dict:
    return json.loads((ROOT / "schema" / "question-file.schema.json").read_text())


def _is_date(value: str) -> bool:
    try:
        dt.date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def validate(files: dict[str, dict], exams: dict, kg: dict | None = None,
             base: dict[str, dict] | None = None) -> Report:
    report = Report()
    validator = jsonschema.Draft202012Validator(_schema())
    seen: dict[str, str] = {}
    current: dict[str, dict] = {}

    for rel, doc in files.items():
        errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        for e in errs:
            report.error(rel, f"schema: {'/'.join(map(str, e.path)) or '<root>'}: {e.message}")
        if errs:
            continue

        article = doc["article"]
        slug = article.split(":", 1)[1]
        if Path(rel).stem != slug:
            report.error(rel, f"file name must match the article slug ({slug}.yaml)")
        art = None
        if kg is not None:
            art = kg.get(article)
            if art is None:
                report.error(rel, f"article {article} not found in the knowledge graph")
            elif Path(rel).parent.name != art.get("domain"):
                report.error(rel, f"file must live in questions/{art.get('domain')}/")

        for q in doc["questions"]:
            where = f"{rel}#{q['id']}"
            if q["id"] in seen:
                report.error(where, f"duplicate id (also in {seen[q['id']]})")
            seen[q["id"]] = rel
            current[q["id"]] = q

            if not q["id"].startswith(slug + "-"):
                report.error(where, f"id must start with '{slug}-'")
            if not (_is_date(q["created"]) and _is_date(q["updated"])):
                report.error(where, "created/updated must be YYYY-MM-DD dates")
            elif q["updated"] < q["created"]:
                report.error(where, "updated is earlier than created")

            option_ids = [o["id"] for o in q["options"]]
            expected = [chr(ord("a") + i) for i in range(len(option_ids))]
            if option_ids != expected:
                report.error(where, f"option ids must be {expected} in order")
            texts = [o["text"].strip().lower() for o in q["options"]]
            if len(set(texts)) != len(texts):
                report.error(where, "duplicate option text")
            missing = [a for a in q["answer"] if a not in option_ids]
            if missing:
                report.error(where, f"answer references unknown options {missing}")
            if q["type"] == "single" and len(q["answer"]) != 1:
                report.error(where, "type single needs exactly one answer")
            if q["type"] == "multiple":
                if len(q["answer"]) < 2:
                    report.error(where, "type multiple needs at least two answers")
                if len(q["answer"]) >= len(option_ids):
                    report.error(where, "type multiple cannot mark every option correct")

            for exam in q.get("exams", []):
                if exam not in exams:
                    report.error(where, f"unknown exam '{exam}' (add it to exams.yaml first)")

            if q["status"] == "retired" and not q.get("retiredReason"):
                report.warn(where, "retired question has no retiredReason")

            if art is not None:
                source_ids = {s["id"] for s in art.get("sources", [])}
                bad = [s for s in q["sources"] if s not in source_ids]
                if bad:
                    report.error(where, f"sources {bad} are not defined in {article}")

    if base is not None:
        base_questions = {q["id"]: q for doc in base.values() for q in doc.get("questions", [])}
        for qid, old in base_questions.items():
            new = current.get(qid)
            if new is None:
                report.error(qid, "question id was removed; ids are permanent, set status: retired instead")
                continue
            changed = {k: v for k, v in new.items() if k != "updated"} != {
                k: v for k, v in old.items() if k != "updated"}
            if changed and new["updated"] == old["updated"]:
                report.error(qid, "content changed but 'updated' was not bumped (clients sync on it)")
            if new["created"] != old["created"]:
                report.error(qid, "'created' must not change")

    return report


def _exams_for(q: dict, art: dict | None, exams: dict) -> list[str]:
    tags = list(q.get("exams", []))
    if art:
        by_kg = {v.get("kg"): k for k, v in exams.items() if v.get("kg")}
        for rel in art.get("relations", []) or []:
            if rel.get("predicate") == "coveredBy" and rel.get("object") in by_kg:
                tags.append(by_kg[rel["object"]])
    return sorted(set(tags))


def build(files: dict[str, dict], exams: dict, kg: dict, version: str) -> dict:
    """Compile question files into the API dataset (dist/questions.json)."""
    questions = []
    for doc in files.values():
        art = kg[doc["article"]]
        slug = doc["article"].split(":", 1)[1]
        sources = {s["id"]: s for s in art.get("sources", [])}
        for q in doc["questions"]:
            record = {
                "id": q["id"],
                "status": q["status"],
                "type": q["type"],
                "difficulty": q["difficulty"],
                "stem": q["stem"].strip(),
                "options": [{"id": o["id"], "text": o["text"].strip()} for o in q["options"]],
                "answer": sorted(q["answer"]),
                "explanation": q["explanation"].strip(),
                "domain": art["domain"],
                "exams": _exams_for(q, art, exams),
                "topic": {
                    "id": doc["article"],
                    "title": art["title"],
                    "url": KG_SITE.format(slug=slug),
                },
                "sources": [
                    {"title": sources[s]["title"], "publisher": sources[s].get("publisher"),
                     "url": sources[s]["url"]}
                    for s in q["sources"]
                ],
                "release": art.get("release"),
                "created": q["created"],
                "updated": q["updated"],
            }
            if q["status"] == "retired":
                record["retiredReason"] = q.get("retiredReason")
            questions.append(record)

    questions.sort(key=lambda r: r["id"])
    published = [q for q in questions if q["status"] == "published"]
    return {
        "meta": {
            "apiVersion": API_VERSION,
            "datasetVersion": version,
            "generatedAt": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
            "lastUpdated": max((q["updated"] for q in questions), default=None),
            "questionCount": len(published),
            "retiredCount": len(questions) - len(published),
            "license": CONTENT_LICENSE,
            "attribution": ATTRIBUTION,
            "sourceGraph": KG_REPO,
        },
        "exams": {k: {"name": v["name"]} for k, v in exams.items()},
        "questions": questions,
    }
