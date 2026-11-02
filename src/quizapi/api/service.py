"""Endpoint logic, free of AWS so it can be unit tested directly."""
from __future__ import annotations

import base64
import datetime as dt
import random
import re

DIFFICULTIES = {"easy", "medium", "hard"}
MAX_LIMIT = 100
MAX_RANDOM = 50


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _bool(value, name: str) -> bool:
    if value is None:
        return False
    if str(value).lower() in ("true", "1"):
        return True
    if str(value).lower() in ("false", "0"):
        return False
    raise ApiError(400, "invalid_parameter", f"{name} must be true or false")


def _int(value, name: str, default: int, lo: int, hi: int) -> int:
    if value is None:
        return default
    try:
        n = int(value)
    except ValueError:
        raise ApiError(400, "invalid_parameter", f"{name} must be an integer") from None
    if not lo <= n <= hi:
        raise ApiError(400, "invalid_parameter", f"{name} must be between {lo} and {hi}")
    return n


def _date(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    try:
        return dt.date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        raise ApiError(400, "invalid_parameter", f"{name} must be a date (YYYY-MM-DD)") from None


def _encode_cursor(last_id: str) -> str:
    return base64.urlsafe_b64encode(last_id.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> str:
    try:
        value = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True).decode()
    except Exception:
        value = ""
    if not re.fullmatch(r"[a-z0-9-]+", value):
        raise ApiError(400, "invalid_cursor", "cursor is not valid; restart from the first page")
    return value


def present(q: dict, include_answers: bool, shuffle: bool = False, rng: random.Random | None = None) -> dict:
    out = {k: v for k, v in q.items() if include_answers or k not in ("answer", "explanation")}
    if shuffle:
        options = list(out["options"])
        (rng or random).shuffle(options)
        out["options"] = options
    return out


class QuizService:
    def __init__(self, repo, rng: random.Random | None = None):
        self.repo = repo
        self.rng = rng or random.Random()

    def _filter(self, ds, params: dict, include_retired: bool = False) -> list[dict]:
        exam, domain = params.get("exam"), params.get("domain")
        topic, difficulty = params.get("topic"), params.get("difficulty")
        if exam and exam not in ds.exams:
            raise ApiError(400, "invalid_parameter", f"unknown exam '{exam}'; see GET /v1/exams")
        if difficulty and difficulty not in DIFFICULTIES:
            raise ApiError(400, "invalid_parameter", "difficulty must be easy, medium or hard")
        since = _date(params.get("updatedSince"), "updatedSince")
        out = []
        for q in ds.questions:
            if q["status"] == "retired" and not (include_retired or since):
                continue
            if exam and exam not in q["exams"]:
                continue
            if domain and q["domain"] != domain:
                continue
            if topic and q["topic"]["id"] != topic:
                continue
            if difficulty and q["difficulty"] != difficulty:
                continue
            if since and q["updated"] < since:
                continue
            out.append(q)
        return out

    def list_questions(self, params: dict) -> dict:
        ds = self.repo.load()
        limit = _int(params.get("limit"), "limit", 20, 1, MAX_LIMIT)
        include = _bool(params.get("includeAnswers"), "includeAnswers")
        shuffle = _bool(params.get("shuffleOptions"), "shuffleOptions")
        matches = self._filter(ds, params)
        if params.get("cursor"):
            after = _decode_cursor(params["cursor"])
            matches = [q for q in matches if q["id"] > after]
        page = matches[:limit]
        return {
            "data": [present(q, include, shuffle, self.rng) for q in page],
            "nextCursor": _encode_cursor(page[-1]["id"]) if len(matches) > limit else None,
            "datasetVersion": ds.meta["datasetVersion"],
        }

    def get_question(self, qid: str, params: dict) -> dict:
        ds = self.repo.load()
        q = ds.by_id.get(qid)
        if q is None:
            raise ApiError(404, "not_found", f"no question with id '{qid}'")
        return present(q, _bool(params.get("includeAnswers"), "includeAnswers"),
                       _bool(params.get("shuffleOptions"), "shuffleOptions"), self.rng)

    def random_questions(self, params: dict) -> dict:
        ds = self.repo.load()
        count = _int(params.get("count"), "count", 1, 1, MAX_RANDOM)
        include = _bool(params.get("includeAnswers"), "includeAnswers")
        shuffle = _bool(params.get("shuffleOptions"), "shuffleOptions")
        if params.get("updatedSince"):
            raise ApiError(400, "invalid_parameter", "updatedSince is not supported on /random")
        pool = self._filter(ds, params)
        picked = self.rng.sample(pool, min(count, len(pool)))
        return {"data": [present(q, include, shuffle, self.rng) for q in picked],
                "datasetVersion": ds.meta["datasetVersion"]}

    def check_answer(self, qid: str, body: dict | None) -> dict:
        ds = self.repo.load()
        q = ds.by_id.get(qid)
        if q is None:
            raise ApiError(404, "not_found", f"no question with id '{qid}'")
        selected = (body or {}).get("selected")
        if not isinstance(selected, list) or not selected or not all(isinstance(s, str) for s in selected):
            raise ApiError(400, "invalid_body", 'body must be {"selected": ["<option id>", ...]}')
        valid = {o["id"] for o in q["options"]}
        unknown = sorted(set(selected) - valid)
        if unknown:
            raise ApiError(400, "invalid_body", f"unknown option ids {unknown}")
        return {
            "id": q["id"],
            "correct": sorted(set(selected)) == sorted(q["answer"]),
            "correctOptionIds": q["answer"],
            "explanation": q["explanation"],
            "sources": q["sources"],
            "topic": q["topic"],
        }

    def exams(self) -> dict:
        ds = self.repo.load()
        counts: dict[str, int] = {}
        for q in ds.questions:
            if q["status"] == "published":
                for e in q["exams"]:
                    counts[e] = counts.get(e, 0) + 1
        return {"data": [{"id": k, "name": v["name"], "questionCount": counts.get(k, 0)}
                         for k, v in sorted(ds.exams.items())]}

    def domains(self) -> dict:
        ds = self.repo.load()
        counts: dict[str, int] = {}
        for q in ds.questions:
            if q["status"] == "published":
                counts[q["domain"]] = counts.get(q["domain"], 0) + 1
        return {"data": [{"id": k, "questionCount": v} for k, v in sorted(counts.items())]}

    def meta(self) -> dict:
        return self.repo.load().meta
