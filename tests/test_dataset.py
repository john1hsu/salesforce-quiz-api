import copy

from quizapi import dataset

EXAMS = {"platform-developer-i": {"name": "PD1"},
         "platform-integration-architect": {"name": "IA", "kg": "kt:integration-architect-certification"}}

KG = {"kt:platform-events": {
    "id": "kt:platform-events", "title": "Platform Events", "domain": "integration", "release": "Winter '27",
    "relations": [{"predicate": "coveredBy", "object": "kt:integration-architect-certification"}],
    "sources": [{"id": "s1", "title": "Guide", "publisher": "Salesforce", "url": "https://developer.salesforce.com/x"},
                {"id": "s2", "title": "Basics", "publisher": "Trailhead", "url": "https://trailhead.salesforce.com/y"}],
}}

QUESTION = {
    "id": "platform-events-001", "status": "published", "type": "single", "difficulty": "easy",
    "stem": "Which publish behavior waits for commit?",
    "options": [{"id": "a", "text": "Publish Immediately"}, {"id": "b", "text": "Publish After Commit"},
                {"id": "c", "text": "Publish Later"}],
    "answer": ["b"], "explanation": "Publish After Commit only sends the event if the transaction commits.",
    "exams": ["platform-developer-i"], "sources": ["s1"], "created": "2026-11-02", "updated": "2026-11-02",
}
PATH = "questions/integration/platform-events.yaml"


def files(*questions):
    return {PATH: {"article": "kt:platform-events", "questions": [copy.deepcopy(q) for q in questions]}}


def errors(fs, base=None):
    return dataset.validate(fs, EXAMS, kg=KG, base=base).errors


def test_valid_file_passes():
    assert errors(files(QUESTION)) == []


def test_answer_must_reference_an_option():
    assert any("unknown options" in e for e in errors(files({**QUESTION, "answer": ["e"]})))


def test_single_needs_one_answer_and_multiple_needs_two():
    assert any("exactly one" in e for e in errors(files({**QUESTION, "answer": ["a", "b"]})))
    assert any("at least two" in e for e in errors(files({**QUESTION, "type": "multiple"})))


def test_unknown_exam_and_source():
    assert any("unknown exam" in e for e in errors(files({**QUESTION, "exams": ["made-up"]})))
    assert any("not defined" in e for e in errors(files({**QUESTION, "sources": ["s9"]})))


def test_wrong_folder_or_article():
    fs = {"questions/data-model/platform-events.yaml": files(QUESTION)[PATH]}
    assert any("must live in questions/integration" in e for e in errors(fs))
    fs = {PATH: {"article": "kt:missing", "questions": [QUESTION]}}
    assert any("not found" in e for e in errors(fs))


def test_duplicate_ids():
    assert any("duplicate id" in e for e in errors(files(QUESTION, QUESTION)))


def test_ids_are_permanent():
    assert any("retired instead" in e for e in errors({}, base=files(QUESTION)))


def test_content_change_requires_updated_bump():
    edited = {**QUESTION, "stem": "Which publish behavior waits for the commit?"}
    assert any("not bumped" in e for e in errors(files(edited), base=files(QUESTION)))
    assert errors(files({**edited, "updated": "2026-11-03"}), base=files(QUESTION)) == []


def test_build_adds_exams_from_graph_and_resolves_sources():
    data = dataset.build(files(QUESTION), EXAMS, KG, version="abc")
    q = data["questions"][0]
    assert q["exams"] == ["platform-developer-i", "platform-integration-architect"]
    assert q["sources"][0]["url"] == "https://developer.salesforce.com/x"
    assert q["topic"]["url"].endswith("/articles/platform-events.html")
    assert data["meta"]["questionCount"] == 1 and data["meta"]["license"] == "CC-BY-4.0"


def test_repo_question_files_pass_schema_checks():
    """The committed questions validate (graph checks run in CI with a knowledge-graph checkout)."""
    report = dataset.validate(dataset.load_question_files(), dataset.load_exams())
    assert report.errors == []
