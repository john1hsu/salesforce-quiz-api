import boto3
import pytest
import yaml
from moto import mock_aws

from quizapi.api.handler import ROUTES
from quizapi.api.repository import CachedRepository, DynamoRepository, FileRepository


@pytest.fixture
def table_name(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    with mock_aws():
        boto3.client("dynamodb").create_table(
            TableName="quiz-api-test", BillingMode="PAY_PER_REQUEST",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
        )
        yield "quiz-api-test"


def test_dynamo_round_trip(table_name, dataset_dict):
    repo = DynamoRepository(table_name)
    assert repo.replace_all(dataset_dict) == len(dataset_dict["questions"]) + 1
    ds = repo.load()
    assert ds.meta == dataset_dict["meta"]
    assert [q["id"] for q in ds.questions] == sorted(q["id"] for q in dataset_dict["questions"])
    # Reloading is idempotent.
    repo.replace_all(dataset_dict)
    assert len(repo.load().questions) == len(dataset_dict["questions"])


def test_empty_table_is_an_error(table_name):
    with pytest.raises(RuntimeError):
        DynamoRepository(table_name).load()


def test_cache_respects_ttl(dataset_file):
    now = [0.0]
    calls = []

    class Counting(FileRepository):
        def load(self):
            calls.append(1)
            return super().load()

    repo = CachedRepository(Counting(dataset_file), ttl_seconds=300, clock=lambda: now[0])
    repo.load()
    repo.load()
    now[0] = 301
    repo.load()
    assert len(calls) == 2


def test_every_openapi_path_has_a_route():
    spec = yaml.safe_load(open("openapi/openapi.yaml"))
    for path, ops in spec["paths"].items():
        concrete = path.replace("{id}", "platform-events-001")
        for method in ops:
            assert any(m == method.upper() and p.match(concrete) for m, p, _, _ in ROUTES), (method, path)
