# Salesforce Quiz API

An open, community-run API of **original, citation-backed Salesforce practice questions** that any quiz app,
study bot or LMS can plug into.

Every question is grounded in an article in the
[Salesforce Knowledge Graph](https://john1hsu.github.io/salesforce-knowledge-graph/) and links to the official
Salesforce sources behind its answer, so learners can always check *why*.

- **Docs and API reference:** https://john1hsu.github.io/salesforce-quiz-api/
- **Bulk download:** https://john1hsu.github.io/salesforce-quiz-api/questions.json (for offline apps)
- **Get an API key:** [open a key request](https://github.com/john1hsu/salesforce-quiz-api/issues/new?template=api_key_request.yml)
- **Licence:** questions CC BY 4.0, code MIT

## Quick start

```bash
curl -H "x-api-key: $KEY" "$BASE_URL/v1/questions/random?count=5&exam=platform-developer-i"
curl -H "x-api-key: $KEY" -X POST "$BASE_URL/v1/questions/platform-events-001/check" -d '{"selected":["b"]}'
```

| Endpoint | What it does |
|---|---|
| `GET /v1/questions` | List with filters (`exam`, `domain`, `topic`, `difficulty`, `updatedSince`), cursor pagination |
| `GET /v1/questions/random` | Up to 50 random questions matching the filters |
| `GET /v1/questions/{id}` | One question |
| `POST /v1/questions/{id}/check` | Grade a selection and return the explanation and sources |
| `GET /v1/exams`, `/v1/domains`, `/v1/meta` | Catalog, counts, dataset version and attribution text |

Answers are hidden unless you pass `includeAnswers=true`. Pass `shuffleOptions=true` to randomise option
order. The full contract is in [`openapi/openapi.yaml`](openapi/openapi.yaml), and a runnable client is in
[`examples/javascript`](examples/javascript).

### Guarantees for client apps

- **Permanent ids.** A question id never changes or disappears. Removed questions become `status: retired`.
- **Incremental sync.** Any content change bumps `updated`. Call `GET /v1/questions?updatedSince=<date>`.
- **Versioned.** Breaking changes go to `/v2`; `/v1` stays.
- **Cited.** Every answer links to the sources that support it.

## How it works

```
salesforce-knowledge-graph (articles + sources)
        │  weekly: AI drafts questions ──► pull request ──► human review ──► merge
        ▼
questions/<domain>/<article>.yaml  ──► scripts/quiz.py check + build ──► dist/questions.json
        │
        ├─► GitHub Actions (OIDC) ──► DynamoDB ──► Lambda ──► API Gateway (keys, rate limits)
        └─► GitHub Pages: docs, OpenAPI spec, bulk download
```

| Path | What |
|---|---|
| `questions/` | Question bank, one YAML file per knowledge-graph article |
| `schema/question-file.schema.json` | Question file schema |
| `exams.yaml` | Allowed exam tags, and their mapping to graph certification nodes |
| `scripts/quiz.py` | `check`, `build`, `load`, `coverage` |
| `scripts/generate.py` | Drafts questions with Claude for articles that have none |
| `src/quizapi/api/` | Lambda handler and endpoint logic |
| `infra/` | AWS CDK stack (staging and prod) and the one-time OIDC bootstrap template |
| `openapi/`, `docs/`, `examples/` | API contract, docs site, sample client |

## Develop locally

```bash
pip install -r requirements-dev.txt
git clone https://github.com/john1hsu/salesforce-knowledge-graph ../salesforce-knowledge-graph
python3 scripts/quiz.py check --kg ../salesforce-knowledge-graph
python3 scripts/quiz.py build --kg ../salesforce-knowledge-graph
pytest
```

## Deploying (maintainers)

One-time AWS setup, then every merge to `main` deploys staging, smoke-tests it, and waits for approval
before prod. See [docs/DEPLOYING.md](docs/DEPLOYING.md).

## Contributing

Questions, corrections and code are all welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) first, especially the
rule on exam content: **never submit real exam questions or anything from exam-dump sites.**

## Licence

Code: [MIT](LICENSE). Question content: [CC BY 4.0](LICENSE-CONTENT.md). Not affiliated with or endorsed by
Salesforce.
