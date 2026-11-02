import pytest

from quizapi.api.service import ApiError


def test_list_hides_answers_and_retired_by_default(svc):
    res = svc.list_questions({})
    ids = [q["id"] for q in res["data"]]
    assert "junction-object-003" not in ids
    assert len(ids) == 4
    assert all("answer" not in q and "explanation" not in q for q in res["data"])
    assert res["nextCursor"] is None


def test_include_answers(svc):
    q = svc.list_questions({"includeAnswers": "true"})["data"][0]
    assert q["answer"] and q["explanation"]


def test_filters(svc):
    assert {q["id"] for q in svc.list_questions({"exam": "platform-app-builder"})["data"]} == {
        "junction-object-001", "junction-object-002"}
    assert [q["id"] for q in svc.list_questions({"difficulty": "medium"})["data"]] == ["platform-events-002"]
    assert len(svc.list_questions({"domain": "integration"})["data"]) == 2
    assert len(svc.list_questions({"topic": "kt:platform-events"})["data"]) == 2


def test_unknown_exam_is_400(svc):
    with pytest.raises(ApiError) as e:
        svc.list_questions({"exam": "nope"})
    assert e.value.status == 400


def test_pagination_walks_every_question_once(svc):
    seen, cursor = [], None
    while True:
        params = {"limit": "2"}
        if cursor:
            params["cursor"] = cursor
        res = svc.list_questions(params)
        seen += [q["id"] for q in res["data"]]
        cursor = res["nextCursor"]
        if not cursor:
            break
    assert seen == sorted(seen) and len(seen) == len(set(seen)) == 4


def test_bad_cursor_and_limit(svc):
    with pytest.raises(ApiError):
        svc.list_questions({"cursor": "!!!"})
    with pytest.raises(ApiError):
        svc.list_questions({"limit": "500"})


def test_updated_since_includes_retired_for_sync(svc):
    ids = {q["id"] for q in svc.list_questions({"updatedSince": "2026-11-01"})["data"]}
    assert ids == {"platform-events-001", "junction-object-001", "junction-object-002", "junction-object-003"}


def test_random(svc):
    res = svc.random_questions({"count": "3", "exam": "platform-developer-i"})
    assert len(res["data"]) == 2  # only two match; never errors when count exceeds pool
    assert all(q["id"].startswith("platform-events") for q in res["data"])


def test_shuffle_keeps_option_ids(svc):
    q = svc.get_question("platform-events-001", {"shuffleOptions": "true"})
    assert sorted(o["id"] for o in q["options"]) == ["a", "b", "c"]


def test_get_unknown_is_404(svc):
    with pytest.raises(ApiError) as e:
        svc.get_question("nope-001", {})
    assert e.value.status == 404


def test_check_single_and_multiple(svc):
    assert svc.check_answer("platform-events-001", {"selected": ["a"]})["correct"] is True
    assert svc.check_answer("platform-events-001", {"selected": ["b"]})["correct"] is False
    assert svc.check_answer("junction-object-002", {"selected": ["b", "a"]})["correct"] is True
    assert svc.check_answer("junction-object-002", {"selected": ["a"]})["correct"] is False


def test_check_validates_body(svc):
    for body in (None, {}, {"selected": []}, {"selected": "a"}, {"selected": ["z"]}):
        with pytest.raises(ApiError):
            svc.check_answer("platform-events-001", body)


def test_exams_and_domains(svc):
    exams = {e["id"]: e["questionCount"] for e in svc.exams()["data"]}
    assert exams == {"platform-app-builder": 2, "platform-developer-i": 2}
    assert {d["id"]: d["questionCount"] for d in svc.domains()["data"]} == {"data-model": 2, "integration": 2}
