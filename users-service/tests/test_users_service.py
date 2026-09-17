import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from users_service.app import create_app


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "users_test.db")
    app = create_app(db_path=db_path)
    app.testing = True
    with app.test_client() as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_create_user(client):
    resp = client.post("/users", json={"name": "Ada Lovelace", "email": "ada@example.com"})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["name"] == "Ada Lovelace"
    assert body["email"] == "ada@example.com"
    assert isinstance(body["id"], int)


def test_create_user_missing_fields(client):
    resp = client.post("/users", json={"name": "No Email"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_user_duplicate_email_conflicts(client):
    client.post("/users", json={"name": "First", "email": "dup@example.com"})
    resp = client.post("/users", json={"name": "Second", "email": "dup@example.com"})
    assert resp.status_code == 409


def test_list_users(client):
    client.post("/users", json={"name": "A", "email": "a@example.com"})
    client.post("/users", json={"name": "B", "email": "b@example.com"})
    resp = client.get("/users")
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body) == 2
    assert {u["email"] for u in body} == {"a@example.com", "b@example.com"}


def test_get_user_by_id(client):
    created = client.post("/users", json={"name": "Grace Hopper", "email": "grace@example.com"}).get_json()
    resp = client.get(f"/users/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Grace Hopper"


def test_get_user_not_found(client):
    resp = client.get("/users/9999")
    assert resp.status_code == 404


def test_update_user(client):
    created = client.post("/users", json={"name": "Old Name", "email": "old@example.com"}).get_json()
    resp = client.put(f"/users/{created['id']}", json={"name": "New Name"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["name"] == "New Name"
    assert body["email"] == "old@example.com"


def test_update_user_not_found(client):
    resp = client.put("/users/9999", json={"name": "Ghost"})
    assert resp.status_code == 404


def test_delete_user(client):
    created = client.post("/users", json={"name": "Temp", "email": "temp@example.com"}).get_json()
    resp = client.delete(f"/users/{created['id']}")
    assert resp.status_code == 204
    assert client.get(f"/users/{created['id']}").status_code == 404


def test_delete_user_not_found(client):
    resp = client.delete("/users/9999")
    assert resp.status_code == 404
