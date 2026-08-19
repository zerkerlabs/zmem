// Print the file of the first failing spec in a Playwright JSON report (or ''),
// so CI can point `vigilis heal` at the spec that actually failed.
// Usage: node ci-first-failing.mjs [results.json]
import { readFileSync } from 'node:fs';

const path = process.argv[2] ?? 'results.json';
const report = JSON.parse(readFileSync(path, 'utf8'));
const failing = [];

const walk = (suite) => {
  for (const spec of suite.specs ?? []) {
    if (spec.ok === false) failing.push(spec.file ?? suite.file ?? '');
  }
  for (const child of suite.suites ?? []) walk(child);
};

for (const suite of report.suites ?? []) walk(suite);
process.stdout.write(failing[0] ?? '');
