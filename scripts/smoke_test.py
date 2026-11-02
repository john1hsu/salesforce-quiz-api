#!/usr/bin/env python3
"""End-to-end check against a deployed stage.

  python3 scripts/smoke_test.py https://<id>.execute-api.<region>.amazonaws.com/staging/ <api-key>
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


def call(base: str, key: str | None, method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(
        base.rstrip("/") + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **({"x-api-key": key} if key else {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return res.status, json.loads(res.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None


def main() -> int:
    base, key = sys.argv[1], sys.argv[2]
    failures = []

    def expect(label, cond):
        print(("ok   " if cond else "FAIL ") + label)
        if not cond:
            failures.append(label)

    status, _ = call(base, None, "GET", "/v1/meta")
    expect("requests without a key are rejected (403)", status == 403)

    status, meta = call(base, key, "GET", "/v1/meta")
    expect("GET /v1/meta", status == 200 and meta and meta.get("questionCount", 0) > 0)

    status, page = call(base, key, "GET", "/v1/questions?limit=2")
    expect("GET /v1/questions hides answers", status == 200 and page["data"] and "answer" not in page["data"][0])

    status, rnd = call(base, key, "GET", "/v1/questions/random?count=1&includeAnswers=true")
    expect("GET /v1/questions/random", status == 200 and len(rnd["data"]) == 1)
    q = rnd["data"][0]

    status, one = call(base, key, "GET", f"/v1/questions/{q['id']}")
    expect("GET /v1/questions/{id}", status == 200 and one["id"] == q["id"])

    status, res = call(base, key, "POST", f"/v1/questions/{q['id']}/check", {"selected": q["answer"]})
    expect("POST /v1/questions/{id}/check grades correctly", status == 200 and res["correct"] is True)

    status, _ = call(base, key, "GET", "/v1/questions/does-not-exist-001")
    expect("unknown id returns 404", status == 404)

    print(f"{len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
