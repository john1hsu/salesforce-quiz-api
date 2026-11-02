# JavaScript sample client

A terminal quiz in one file with no dependencies (Node 18+). It pulls random questions, grades answers with
`POST /check`, links each topic's knowledge-graph article, and shows the required attribution.

```bash
export QUIZ_API_URL=https://<id>.execute-api.us-east-1.amazonaws.com/prod
export QUIZ_API_KEY=<your key>
node quiz.mjs --exam platform-developer-i --count 5
```

Filters: `--exam <slug>` (see `GET /v1/exams`), `--domain <id>`, `--count <1-50>`.

The same calls work from a browser: the API sends CORS headers. Remember that a key in browser code is
visible to users. Community keys are rate-limited and read-only, but don't reuse a key you want kept private.
