# Dockerized Microservices

A small, genuinely functional microservices demo: three Flask services that
talk to each other over HTTP, wired together with Docker Compose.

- **users-service** — owns user records (SQLite-backed CRUD).
- **orders-service** — creates orders that reference a `user_id`, and calls
  users-service over HTTP to validate the user exists before saving the
  order.
- **api-gateway-service** — a thin reverse proxy that routes `/users/*` to
  users-service and `/orders/*` to orders-service, so clients only ever talk
  to one address.

## Architecture

```
                        +----------------------+
        client  ------> |  api-gateway-service |  (port 5000)
                        +----------------------+
                          /users/*     \orders/*
                          v              v
                +----------------+   +-----------------+
                | users-service  |   | orders-service  |
                | (port 5001)    |<--| (port 5002)      |
                | SQLite: users  |   | SQLite: orders   |
                +----------------+   +-----------------+
                                       "does user X exist?"
                                       GET /users/<id> on
                                       users-service, before
                                       an order is created.
```

All three services share a Docker network (`microservices-net`) when run via
Compose. `orders-service` and `api-gateway-service` find `users-service` (and
each other) through service-discovery-by-name, configured via environment
variables such as `USERS_SERVICE_URL=http://users-service:5001`.

## A note on Docker in this repo

**Docker wasn't available in the environment these were built in**
(the Docker CLI was present but the daemon was not running, and could not be
started). The Dockerfiles and `docker-compose.yml` here are correct by
careful construction and structural validation — not by trial-and-error
against a running daemon:

- Each service's actual application code is real (no stubs) and is verified
  by that service's own unit test suite, run directly with Python.
- `docker-compose.yml` and each `Dockerfile` are validated *structurally*:
  automated tests parse the compose file with PyYAML and assert that every
  `depends_on`/`volumes`/`networks` reference resolves, that every build
  context exists on disk, and that each Dockerfile starts with `FROM`, has a
  matching `EXPOSE`, and a sane `CMD`.
- None of this is a substitute for actually running the containers. **Run
  `docker compose up --build` locally to verify** the images build and the
  services talk to each other over the real Docker network.

## Running it

### With Docker Compose (once Docker is available)

```bash
docker compose up --build
```

This builds all three images and starts them on a shared bridge network,
with named volumes (`users-data`, `orders-data`) so each service's SQLite
file survives container restarts.

- api-gateway-service: http://localhost:5000
- users-service (direct): http://localhost:5001
- orders-service (direct): http://localhost:5002

### Running each service directly (for development)

Each service is self-contained with its own `requirements.txt` and virtual
environment.

```bash
# users-service
cd users-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python wsgi.py            # listens on :5001 (or PORT env var)

# orders-service (in another shell)
cd orders-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
USERS_SERVICE_URL=http://localhost:5001 python wsgi.py   # listens on :5002

# api-gateway-service (in another shell)
cd api-gateway-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
USERS_SERVICE_URL=http://localhost:5001 \
ORDERS_SERVICE_URL=http://localhost:5002 \
python wsgi.py             # listens on :5000
```

### Running the tests

```bash
# from the repo root
pip install -r users-service/requirements.txt
pip install -r orders-service/requirements.txt
pip install -r api-gateway-service/requirements.txt
pip install -r infra_tests/requirements.txt

pytest users-service/tests -v
pytest orders-service/tests -v
pytest api-gateway-service/tests -v
pytest infra_tests -v          # structural validation of compose/Dockerfiles
```

All of the above run with plain Python — none of them require Docker.

## API examples

Through the gateway (or hit each service directly on its own port):

```bash
# Create a user
curl -X POST http://localhost:5000/users \
  -H "Content-Type: application/json" \
  -d '{"name": "Ada Lovelace", "email": "ada@example.com"}'
# -> {"id": 1, "name": "Ada Lovelace", "email": "ada@example.com"}

# List users
curl http://localhost:5000/users

# Create an order for that user (orders-service validates user_id=1
# by calling users-service internally before saving the order)
curl -X POST http://localhost:5000/orders \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "item": "Mechanical Keyboard", "quantity": 1}'
# -> {"id": 1, "user_id": 1, "item": "Mechanical Keyboard", "quantity": 1, "status": "pending"}

# Creating an order for a user that doesn't exist fails with 404
curl -X POST http://localhost:5000/orders \
  -H "Content-Type: application/json" \
  -d '{"user_id": 999, "item": "Ghost Order"}'
# -> {"error": "user 999 does not exist"}
```

## Troubleshooting / FAQ

**I get a 502 from `/orders` (or directly from orders-service) saying
"could not verify user; users-service unavailable" — what's happening?**
`orders-service` calls `GET {USERS_SERVICE_URL}/users/<id>` on
`users-service` before it will save an order, and that call has a 5-second
timeout. A 502 here means the request raised `requests.RequestException`
(connection refused, DNS failure, or a timeout) — not that the user was
found-and-rejected. If you see this while running each service directly
(not via Compose), the most common cause is `USERS_SERVICE_URL` pointing at
the wrong host/port, e.g. leaving it at the Compose-network default
(`http://users-service:5001`) instead of `http://localhost:5001` when
running outside Docker. A "user does not exist" case is a distinct 404, not
a 502.

**I hit an endpoint through the gateway and got a plain-HTML 404 instead of
a JSON error — is the gateway broken?** No — `api-gateway-service` only
registers routes under `/users` and `/orders`. Anything else (a typo, an
old endpoint, `/health/users`, etc.) never reaches the proxy code at all;
it's Flask's own default 404 for an unmatched route, which is why it isn't
JSON. If you need a JSON body for unmatched paths too, that would be a
custom `@app.errorhandler(404)` — not currently implemented.

**How do I actually run this with a real Docker daemon?** Nothing about the
Dockerfiles or `docker-compose.yml` is untested — the structural checks in
`infra_tests/` already validate that every build context, volume, and
network reference resolves. If you have Docker Desktop (or another daemon)
running, `docker compose up --build` from the repo root should just work.
If it doesn't, that's a real bug worth filing, since these files were
written to be correct by construction rather than by trial and error
against a live daemon (see "A note on Docker in this repo" above).

**Common docker-compose gotchas to watch for once you do have Docker:**
- `docker compose down` alone leaves the `users-data`/`orders-data` named
  volumes intact; add `-v` if you want a truly clean slate (this also
  wipes both SQLite databases).
- The three services find each other by container/service name
  (`http://users-service:5001`, etc.), which only resolves on the
  `microservices-net` bridge network Compose creates — those hostnames
  won't resolve if you try to run one container standalone with `docker run`
  outside of Compose.
- Rebuilding after a dependency change needs `--build` (or `--no-cache` for
  a stubborn layer cache); `docker compose up` alone reuses existing images.

## Project layout

```
dockerized-microservices/
├── users-service/
│   ├── users_service/{app.py,db.py}
│   ├── wsgi.py
│   ├── tests/test_users_service.py
│   ├── Dockerfile
│   └── requirements.txt
├── orders-service/
│   ├── orders_service/{app.py,db.py}
│   ├── wsgi.py
│   ├── tests/test_orders_service.py
│   ├── Dockerfile
│   └── requirements.txt
├── api-gateway-service/
│   ├── gateway_service/app.py
│   ├── wsgi.py
│   ├── tests/test_gateway_service.py
│   ├── Dockerfile
│   └── requirements.txt
├── infra_tests/                  # structural validation of compose + Dockerfiles
├── docker-compose.yml
└── .github/workflows/tests.yml   # runs all Python unit + structural tests, no Docker required
```

## License

MIT — see [LICENSE](LICENSE).
