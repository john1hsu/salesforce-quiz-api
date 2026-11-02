# Contributing

Thanks for helping. There are three ways to contribute.

## 1. Report a wrong or unclear question

Open a [question correction](https://github.com/john1hsu/salesforce-quiz-api/issues/new?template=question_correction.yml)
with the question id and a source showing what's wrong. Salesforce changes three times a year, so
"this changed in the latest release" reports are especially valuable.

## 2. Add or edit questions

Questions live in `questions/<domain>/<article-slug>.yaml`, one file per article in the
[Salesforce Knowledge Graph](https://github.com/john1hsu/salesforce-knowledge-graph). A question can only be
written for a topic that has an article, because its answer must be supported by that article's sources. If
the topic is missing, suggest it in the knowledge-graph repo first.

### Rules

- **Original content only.** Never submit real certification exam questions, paraphrases of them, or
  anything from exam-dump sites. Salesforce's exam agreements prohibit sharing exam content, and PRs that look
  like it are closed.
- **Grounded and cited.** The answer must follow from the article. List the article source ids that support
  it in `sources`.
- **One idea per question.** Prefer short scenarios over bare recall.
- **Plausible distractors** that are clearly wrong per the article. Vary where the correct answer sits.
- **`single`** questions have 4 options and one answer. **`multiple`** questions say "(Choose 2.)" in the stem.
- **Exam tags** must exist in `exams.yaml`. Exams the article is `coveredBy` in the graph are added automatically.

### Ids are permanent

Apps store question ids, so:

- New ids are `<article-slug>-NNN`, continuing the file's numbering.
- **Never delete or renumber a question.** To remove one, set `status: retired` and add `retiredReason`.
- **Any content change must bump `updated`** to today's date. Never change `created`.

CI enforces all three by comparing your branch with `main`.

### Example

```yaml
article: kt:platform-events
questions:
  - id: platform-events-004
    status: published
    type: single
    difficulty: medium
    stem: >-
      An integration publishes platform events from a trigger, and a subscriber must read the records saved
      in that transaction. Which publish behavior should the event use?
    options:
      - {id: a, text: "Publish Immediately"}
      - {id: b, text: "Publish After Commit"}
      - {id: c, text: "Publish Immediately with a batch size of 1"}
      - {id: d, text: "Publish On Rollback"}
    answer: [b]
    explanation: >-
      Publish After Commit only sends the event if the transaction commits, so the subscriber can read the
      committed records. Publish Immediately sends even if the transaction later fails.
    exams: [platform-developer-i]
    sources: [s2]
    created: 2026-11-02
    updated: 2026-11-02
```

### Check your work

```bash
pip install -r requirements-dev.txt
git clone https://github.com/john1hsu/salesforce-knowledge-graph ../salesforce-knowledge-graph
python3 scripts/quiz.py check --kg ../salesforce-knowledge-graph --base-ref origin/main
```

## 3. Improve the code

Run `ruff check .` and `pytest` before opening a PR. API changes must update `openapi/openapi.yaml`, and
must not break `/v1` clients: add fields, never remove or rename them.

## Review and publishing

Every change, including AI-drafted questions from the weekly generator, goes through a pull request and a
human review. Merging to `main` publishes to staging, then production after approval.

By contributing you agree that your question content is licensed CC BY 4.0 and your code MIT, and that you
will follow the [Code of Conduct](CODE_OF_CONDUCT.md).
