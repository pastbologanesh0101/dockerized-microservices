# Contributing

Thanks for looking at this project. It's a small demo, so the contribution
process is deliberately lightweight.

## Running the tests

You do **not** need Docker installed or running to validate almost
everything in this repo. Each service's Flask app is tested directly with
its own `test_client()`, and the `docker-compose.yml` / Dockerfiles are
validated structurally with PyYAML + plain file parsing, not by building
images. This mirrors what CI (`.github/workflows/tests.yml`) does:

```bash
# from the repo root, one virtualenv is enough for all four suites
python -m venv .venv && source .venv/bin/activate

pip install -r users-service/requirements.txt
pip install -r orders-service/requirements.txt
pip install -r api-gateway-service/requirements.txt
pip install -r infra_tests/requirements.txt

pytest users-service/tests -v
pytest orders-service/tests -v
pytest api-gateway-service/tests -v
pytest infra_tests -v
```

Run each service's suite separately (as above), not as one combined
`pytest` invocation from the root — the three `tests/` packages share a
module name and will collide if pytest is pointed at all of them at once.

If you *do* have a working Docker daemon and want to sanity-check the
Compose setup for real, `docker compose up --build` from the repo root is
the way to do it — but that step is optional and outside what the test
suite (or CI) covers.

## Code style

- Match the existing style in each `app.py`: small, explicit Flask route
  functions, `request.get_json(silent=True) or {}` for parsing input, and
  a `jsonify(error=...)` plus the right HTTP status code for failures.
- Keep each service's Flask app behind a `create_app(...)` factory function
  so tests can construct it with a temp database path / mocked upstream
  URLs instead of touching real files or the network.
- New behavior should come with a new test in the relevant `tests/`
  directory (or `infra_tests/` for compose/Dockerfile changes) — this repo
  has no untested application code, and additions should keep it that way.
- Prefer plain `requests`/`sqlite3` calls over adding new dependencies;
  each service's `requirements.txt` is intentionally short.

## Submitting changes

1. Fork/branch, make your change, and add or update tests alongside it.
2. Run the pytest commands above and confirm everything is green.
3. If you touched `docker-compose.yml` or a `Dockerfile`, also run
   `pytest infra_tests -v` — those tests catch dangling references (missing
   build contexts, undeclared volumes/networks, mismatched ports) without
   needing Docker itself.
4. Open a PR with a short description of what changed and why.
