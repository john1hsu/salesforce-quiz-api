"""AWS Lambda entry point for API Gateway (REST API, Lambda proxy integration)."""
from __future__ import annotations

import json
import logging
import re

from .repository import from_environment
from .service import ApiError, QuizService

log = logging.getLogger()
log.setLevel(logging.INFO)

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,X-Api-Key",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

_service: QuizService | None = None


def service() -> QuizService:
    global _service
    if _service is None:
        _service = QuizService(from_environment())
    return _service


def _response(status: int, body: dict, cache: bool = False) -> dict:
    headers = {"Content-Type": "application/json; charset=utf-8", **CORS}
    headers["Cache-Control"] = "public, max-age=300" if cache else "no-store"
    return {"statusCode": status, "headers": headers, "body": json.dumps(body, ensure_ascii=False)}


ROUTES = [
    ("GET", re.compile(r"^/v1/questions$"), lambda s, m, q, b: s.list_questions(q), True),
    ("GET", re.compile(r"^/v1/questions/random$"), lambda s, m, q, b: s.random_questions(q), False),
    ("GET", re.compile(r"^/v1/questions/([a-z0-9-]+)$"), lambda s, m, q, b: s.get_question(m[1], q), True),
    ("POST", re.compile(r"^/v1/questions/([a-z0-9-]+)/check$"), lambda s, m, q, b: s.check_answer(m[1], b), False),
    ("GET", re.compile(r"^/v1/exams$"), lambda s, m, q, b: s.exams(), True),
    ("GET", re.compile(r"^/v1/domains$"), lambda s, m, q, b: s.domains(), True),
    ("GET", re.compile(r"^/v1/meta$"), lambda s, m, q, b: s.meta(), True),
]


def handler(event, context=None, svc: QuizService | None = None):
    method = event.get("httpMethod", "GET")
    path = (event.get("path") or "/").rstrip("/") or "/"
    params = event.get("queryStringParameters") or {}
    if method == "OPTIONS":
        return {"statusCode": 204, "headers": CORS, "body": ""}
    try:
        body = None
        if method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                raise ApiError(400, "invalid_body", "body must be JSON") from None
        path_matched = False
        for verb, pattern, fn, cacheable in ROUTES:
            m = pattern.match(path)
            if not m:
                continue
            path_matched = True
            if verb == method:
                return _response(200, fn(svc or service(), m, params, body), cache=cacheable)
        if path_matched:
            raise ApiError(405, "method_not_allowed", f"{method} is not allowed on {path}")
        raise ApiError(404, "not_found", f"no route for {path}; see the API docs")
    except ApiError as e:
        return _response(e.status, {"error": {"code": e.code, "message": e.message}})
    except Exception:
        log.exception("unhandled error")
        return _response(500, {"error": {"code": "internal", "message": "internal error"}})
