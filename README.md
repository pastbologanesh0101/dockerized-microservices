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
