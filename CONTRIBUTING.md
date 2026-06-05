# Contributing

Thanks for helping improve Zerker Memory.

## Development Setup

Use Python 3.10 or newer. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e . --no-build-isolation
python3 -m unittest discover -s tests
```

If editable install fails because your local Python environment lacks `wheel`, use:

```bash
python3 setup.py develop
```

## Contribution Guidelines

- Keep changes focused and easy to review.
- Include tests for behavior changes when practical.
- Do not commit local memory databases, logs, or secrets.
- Prefer local-first defaults and explicit trust/authority behavior.
- Update README or integration docs when user-facing commands change.
- Keep `zerker eval` passing; it is the product proof harness.

## Pull Requests

Before opening a pull request, run:

```bash
python3 -m unittest discover -s tests
python3 -m zerker_memory eval
```

In the PR description, summarize the change, note any compatibility impact,
and call out follow-up work separately.
