import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quizapi.api.repository import Dataset  # noqa: E402
from quizapi.api.service import QuizService  # noqa: E402


def _q(qid, domain="integration", exams=("platform-developer-i",), difficulty="easy",
       status="published", updated="2026-11-02", answer=("a",), qtype="single"):
    return {
        "id": qid, "status": status, "type": qtype, "difficulty": difficulty,
        "stem": f"Stem for {qid}?",
        "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}, {"id": "c", "text": "C"}],
        "answer": list(answer), "explanation": f"Because {qid}.",
        "domain": domain, "exams": list(exams),
        "topic": {"id": f"kt:{qid.rsplit('-', 1)[0]}", "title": "T", "url": "https://example.com"},
        "sources": [{"title": "S", "publisher": "Salesforce", "url": "https://help.salesforce.com/x"}],
        "release": "Winter '27", "created": "2026-10-01", "updated": updated,
    }


@pytest.fixture
def dataset_dict():
    questions = [
        _q("platform-events-001"),
        _q("platform-events-002", difficulty="medium", updated="2026-10-15"),
        _q("junction-object-001", domain="data-model", exams=("platform-app-builder",)),
        _q("junction-object-002", domain="data-model", exams=("platform-app-builder",),
           answer=("a", "b"), qtype="multiple"),
        _q("junction-object-003", domain="data-model", status="retired", updated="2026-11-01"),
    ]
    return {
        "meta": {"apiVersion": "v1", "datasetVersion": "test", "license": "CC-BY-4.0"},
        "exams": {"platform-developer-i": {"name": "Platform Developer I"},
                  "platform-app-builder": {"name": "Platform App Builder"}},
        "questions": questions,
    }


class StaticRepo:
    def __init__(self, data):
        self.ds = Dataset.from_dict(data)

    def load(self):
        return self.ds


@pytest.fixture
def svc(dataset_dict):
    return QuizService(StaticRepo(dataset_dict), rng=random.Random(7))


@pytest.fixture
def dataset_file(tmp_path, dataset_dict):
    p = tmp_path / "questions.json"
    p.write_text(json.dumps(dataset_dict))
    return p
