"""Where the dataset lives.

The dataset is small (thousands of questions at most) and read-only for the API, so the Lambda reads
the whole table once per container and caches it for CACHE_SECONDS. Filtering, pagination and random
selection then happen in memory. If the dataset ever grows past roughly 10k questions, add GSIs
(domain, exam) and query them instead of scanning.

Table layout (single table, partition key `pk`):
  pk = "META"          -> {"meta": <json>, "exams": <json>}
  pk = "Q#<id>"        -> {"data": <question json>}
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


class Dataset:
    def __init__(self, meta: dict, exams: dict, questions: list[dict]):
        self.meta = meta
        self.exams = exams
        self.questions = sorted(questions, key=lambda q: q["id"])
        self.by_id = {q["id"]: q for q in self.questions}

    @classmethod
    def from_dict(cls, data: dict) -> Dataset:
        return cls(data["meta"], data.get("exams", {}), data["questions"])


class FileRepository:
    """Serves dist/questions.json. Used by tests and local development."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> Dataset:
        return Dataset.from_dict(json.loads(self.path.read_text()))


class DynamoRepository:
    def __init__(self, table_name: str, client=None):
        import boto3  # available in the Lambda runtime

        self.table_name = table_name
        self.table = (client or boto3.resource("dynamodb")).Table(table_name)

    def load(self) -> Dataset:
        meta, exams, questions = {}, {}, []
        kwargs = {}
        while True:
            page = self.table.scan(**kwargs)
            for item in page["Items"]:
                if item["pk"] == "META":
                    meta = json.loads(item["meta"])
                    exams = json.loads(item["exams"])
                elif item["pk"].startswith("Q#"):
                    questions.append(json.loads(item["data"]))
            if "LastEvaluatedKey" not in page:
                break
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        if not meta:
            raise RuntimeError(f"table {self.table_name} has no META item; run scripts/quiz.py load")
        return Dataset(meta, exams, questions)

    def replace_all(self, data: dict) -> int:
        """Upsert every question and the META item. Ids are permanent (retired, never deleted),
        so nothing is removed; stray items are reported instead."""
        incoming = {f"Q#{q['id']}" for q in data["questions"]}
        with self.table.batch_writer(overwrite_by_pkeys=["pk"]) as batch:
            for q in data["questions"]:
                batch.put_item(Item={"pk": f"Q#{q['id']}", "data": json.dumps(q, ensure_ascii=False)})
            batch.put_item(Item={
                "pk": "META",
                "meta": json.dumps(data["meta"], ensure_ascii=False),
                "exams": json.dumps(data.get("exams", {}), ensure_ascii=False),
            })
        existing = set()
        kwargs = {"ProjectionExpression": "pk"}
        while True:
            page = self.table.scan(**kwargs)
            existing |= {i["pk"] for i in page["Items"] if i["pk"].startswith("Q#")}
            if "LastEvaluatedKey" not in page:
                break
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        stray = existing - incoming
        if stray:
            print(f"warning: {len(stray)} items in the table are not in the dataset: {sorted(stray)[:10]}")
        return len(incoming) + 1


class CachedRepository:
    def __init__(self, inner, ttl_seconds: int = 300, clock=time.monotonic):
        self.inner = inner
        self.ttl = ttl_seconds
        self.clock = clock
        self._data: Dataset | None = None
        self._loaded_at = 0.0

    def load(self) -> Dataset:
        now = self.clock()
        if self._data is None or now - self._loaded_at > self.ttl:
            self._data = self.inner.load()
            self._loaded_at = now
        return self._data


def from_environment():
    if os.environ.get("QUIZ_DATASET_FILE"):
        inner = FileRepository(os.environ["QUIZ_DATASET_FILE"])
    else:
        inner = DynamoRepository(os.environ["QUIZ_TABLE"])
    return CachedRepository(inner, ttl_seconds=int(os.environ.get("CACHE_SECONDS", "300")))
