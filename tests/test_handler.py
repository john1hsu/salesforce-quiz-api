import json

from quizapi.api.handler import handler


def call(svc, method, path, params=None, body=None):
    event = {"httpMethod": method, "path": path, "queryStringParameters": params,
             "body": json.dumps(body) if body is not None else None}
    res = handler(event, None, svc=svc)
    return res["statusCode"], (json.loads(res["body"]) if res["body"] else None), res["headers"]


def test_routes(svc):
    assert call(svc, "GET", "/v1/questions")[0] == 200
    assert call(svc, "GET", "/v1/questions/random", {"count": "2"})[0] == 200
    status, body, headers = call(svc, "GET", "/v1/questions/platform-events-001")
    assert status == 200 and body["id"] == "platform-events-001"
    assert headers["Access-Control-Allow-Origin"] == "*"
    assert headers["Cache-Control"].startswith("public")
    assert call(svc, "GET", "/v1/exams")[0] == 200
    assert call(svc, "GET", "/v1/domains")[0] == 200
    assert call(svc, "GET", "/v1/meta")[1]["license"] == "CC-BY-4.0"


def test_check(svc):
    status, body, headers = call(svc, "POST", "/v1/questions/platform-events-001/check", body={"selected": ["a"]})
    assert status == 200 and body["correct"] is True
    assert headers["Cache-Control"] == "no-store"


def test_errors(svc):
    assert call(svc, "GET", "/v1/nope")[0] == 404
    assert call(svc, "DELETE", "/v1/questions")[0] == 405
    status, body, _ = call(svc, "GET", "/v1/questions", {"limit": "x"})
    assert status == 400 and body["error"]["code"] == "invalid_parameter"
    event = {"httpMethod": "POST", "path": "/v1/questions/platform-events-001/check", "body": "{bad"}
    assert handler(event, None, svc=svc)["statusCode"] == 400


def test_options_preflight(svc):
    assert call(svc, "OPTIONS", "/v1/questions")[0] == 204


def test_from_environment_file(monkeypatch, dataset_file):
    import quizapi.api.handler as h

    monkeypatch.setenv("QUIZ_DATASET_FILE", str(dataset_file))
    monkeypatch.setattr(h, "_service", None)
    res = h.handler({"httpMethod": "GET", "path": "/v1/meta"})
    assert res["statusCode"] == 200 and json.loads(res["body"])["datasetVersion"] == "test"
