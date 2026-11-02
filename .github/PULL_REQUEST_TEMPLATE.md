## What changed

## Checklist

- [ ] `python3 scripts/quiz.py check --kg ../salesforce-knowledge-graph --base-ref origin/main` passes
- [ ] `pytest` and `ruff check .` pass

**For question changes**
- [ ] Questions are original, not taken from real exams or dumps
- [ ] Each answer is supported by the cited article sources
- [ ] No ids removed or renumbered; edited questions have `updated` bumped

**For API changes**
- [ ] `openapi/openapi.yaml` updated
- [ ] No breaking change to `/v1` (fields added, never removed or renamed)
