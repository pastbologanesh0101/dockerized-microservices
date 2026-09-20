# Changelog

## [Unreleased]

- `CONTRIBUTING.md` documenting how to run each test suite and code style
  expectations.
- Additional test coverage: orders-service timeout handling
  (`requests.Timeout`, distinct from a connection error) and api-gateway
  behavior for paths outside `/users*`/`/orders*`.
- orders-service now rejects a non-integer `user_id` with a 400 instead of
  silently persisting it.
- Troubleshooting/FAQ section in the README.

## [0.1.0] - 2026-09-18

Initial commit. Three independent Flask services plus Docker/Compose
wiring and a test suite, all added in one commit:

- **users-service** — Flask + SQLite CRUD for user records
  (`POST/GET /users`, `GET/PUT/DELETE /users/<id>`, `GET /health`), with
  its own `Dockerfile`, `requirements.txt`, and an 11-test suite covering
  creation, duplicate-email conflicts, lookup, update, and delete.
- **orders-service** — Flask + SQLite for orders that reference a
  `user_id`, validating that user against users-service over HTTP
  (`GET {USERS_SERVICE_URL}/users/<id>`) before saving. Ships with a
  12-test suite, including two tests that back the user check with a real
  in-process users-service `test_client()` rather than a mock.
- **api-gateway-service** — a thin Flask reverse proxy forwarding
  `/users/*` to users-service and `/orders/*` to orders-service, relaying
  method, query string, JSON body, status code, and headers (minus a small
  hop-by-hop exclusion list). 9 tests covering proxying, forwarding, and
  upstream-unreachable handling.
- **infra_tests/** — structural (no-Docker-daemon-required) validation of
  `docker-compose.yml` and each `Dockerfile`: build contexts exist, every
  `depends_on`/volume/network reference resolves, and each Dockerfile
  starts with `FROM`, uses a Python base image, installs
  `requirements.txt`, and exposes/binds the port `docker-compose.yml`
  expects.
- `docker-compose.yml` wiring all three services on a shared bridge network
  with named volumes for each SQLite database.
- `.github/workflows/tests.yml` running all four suites (Python 3.11 and
  3.12) on every push and pull request.
- MIT `LICENSE` and a README documenting the architecture, an honest note
  that Docker itself was not run/built in the environment these files were
  authored in, and instructions for running each service directly or via
  Compose.

Total: 32 files, ~1,310 lines, across a single initial commit.
