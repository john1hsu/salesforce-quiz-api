#!/usr/bin/env node
// Minimal terminal quiz built on the Salesforce Quiz API. Node 18+, no dependencies.
//
//   QUIZ_API_URL=https://<id>.execute-api.us-east-1.amazonaws.com/prod QUIZ_API_KEY=... \
//     node quiz.mjs --exam platform-developer-i --count 5

import readline from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";

const BASE = (process.env.QUIZ_API_URL || "").replace(/\/$/, "");
const KEY = process.env.QUIZ_API_KEY;
if (!BASE || !KEY) {
  console.error("Set QUIZ_API_URL and QUIZ_API_KEY.");
  process.exit(1);
}

const args = Object.fromEntries(
  process.argv.slice(2).join(" ").split("--").filter(Boolean).map((s) => s.trim().split(/\s+/))
);

async function api(path, init = {}) {
  const res = await fetch(BASE + path, {
    ...init,
    headers: { "x-api-key": KEY, "Content-Type": "application/json", ...(init.headers || {}) },
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(`${res.status} ${body?.error?.message ?? res.statusText}`);
  return body;
}

const params = new URLSearchParams({ count: args.count ?? "5", shuffleOptions: "true" });
if (args.exam) params.set("exam", args.exam);
if (args.domain) params.set("domain", args.domain);

const meta = await api("/v1/meta");
const { data: questions } = await api(`/v1/questions/random?${params}`);
if (!questions.length) {
  console.log("No questions match those filters yet.");
  process.exit(0);
}

// Line queue, so answers work whether typed interactively or piped in.
const rl = readline.createInterface({ input, terminal: false });
const lines = [];
const waiting = [];
let closed = false;
rl.on("line", (l) => (waiting.length ? waiting.shift()(l) : lines.push(l)));
rl.on("close", () => {
  closed = true;
  while (waiting.length) waiting.shift()("");
});
const ask = (prompt) => {
  output.write(prompt);
  if (lines.length) return Promise.resolve(lines.shift());
  if (closed) return Promise.resolve("");
  return new Promise((resolve) => waiting.push(resolve));
};
let score = 0;

for (const [i, q] of questions.entries()) {
  console.log(`\n${i + 1}/${questions.length}  [${q.difficulty}] ${q.topic.title}`);
  console.log(q.stem);
  for (const o of q.options) console.log(`  ${o.id}) ${o.text}`);
  const hint = q.type === "multiple" ? " (comma-separated)" : "";
  const raw = await ask(`Your answer${hint}: `);
  const selected = raw.split(/[\s,]+/).map((s) => s.trim().toLowerCase()).filter(Boolean);
  if (!selected.length) {
    console.log("Skipped.");
    continue;
  }
  try {
    const result = await api(`/v1/questions/${q.id}/check`, {
      method: "POST",
      body: JSON.stringify({ selected }),
    });
    if (result.correct) score++;
    console.log(result.correct ? "Correct." : `Not quite. Answer: ${result.correctOptionIds.join(", ")}`);
    console.log(result.explanation);
    console.log(`Learn more: ${result.topic.url}`);
  } catch (e) {
    console.log(`Couldn't check that answer: ${e.message}`);
  }
}

rl.close();
console.log(`\nScore: ${score}/${questions.length}`);
console.log(`\n${meta.attribution}`);
