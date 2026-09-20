import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from orders_service.app import create_app

# Make the sibling users-service package importable so one test can exercise
# a real in-process users-service Flask app (via its own test client) instead
# of a mock, without needing a live container.
USERS_SERVICE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "users-service"
)
sys.path.insert(0, os.path.abspath(USERS_SERVICE_DIR))
from users_service.app import create_app as create_users_app  # noqa: E402


class FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "orders_test.db")
    app = create_app(db_path=db_path, users_service_url="http://users-service:5001")
    app.testing = True
    with app.test_client() as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_create_order_missing_fields(client):
    resp = client.post("/orders", json={"item": "Widget"})
    assert resp.status_code == 400


def test_create_order_invalid_quantity(client):
    with patch("orders_service.app.requests.get", return_value=FakeResponse(200)):
        resp = client.post("/orders", json={"user_id": 1, "item": "Widget", "quantity": 0})
    assert resp.status_code == 400


@patch("orders_service.app.requests.get")
def test_create_order_valid_user(mock_get, client):
    mock_get.return_value = FakeResponse(200)
    resp = client.post("/orders", json={"user_id": 1, "item": "Widget", "quantity": 3})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["user_id"] == 1
    assert body["item"] == "Widget"
    assert body["quantity"] == 3
    assert body["status"] == "pending"
    mock_get.assert_called_once_with("http://users-service:5001/users/1", timeout=5)


@patch("orders_service.app.requests.get")
def test_create_order_user_not_found(mock_get, client):
    mock_get.return_value = FakeResponse(404)
    resp = client.post("/orders", json={"user_id": 999, "item": "Widget"})
    assert resp.status_code == 404
    assert "does not exist" in resp.get_json()["error"]


@patch("orders_service.app.requests.get")
def test_create_order_users_service_unreachable(mock_get, client):
    import requests

    mock_get.side_effect = requests.ConnectionError("boom")
    resp = client.post("/orders", json={"user_id": 1, "item": "Widget"})
    assert resp.status_code == 502


@patch("orders_service.app.requests.get")
def test_create_order_users_service_times_out(mock_get, client):
    """A slow/unresponsive users-service should surface as 502, same as a
    connection error, not hang or raise an unhandled exception. requests.Timeout
    is a distinct exception from ConnectionError, so it needs its own case."""
    import requests

    mock_get.side_effect = requests.Timeout("timed out waiting for users-service")
    resp = client.post("/orders", json={"user_id": 1, "item": "Widget"})
    assert resp.status_code == 502
    assert "unavailable" in resp.get_json()["error"]


@patch("orders_service.app.requests.get")
def test_list_and_get_order(mock_get, client):
    mock_get.return_value = FakeResponse(200)
    created = client.post("/orders", json={"user_id": 1, "item": "Gadget"}).get_json()

    listed = client.get("/orders")
    assert listed.status_code == 200
    assert len(listed.get_json()) == 1

    fetched = client.get(f"/orders/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.get_json()["item"] == "Gadget"


def test_get_order_not_found(client):
    resp = client.get("/orders/9999")
    assert resp.status_code == 404


@patch("orders_service.app.requests.get")
def test_delete_order(mock_get, client):
    mock_get.return_value = FakeResponse(200)
    created = client.post("/orders", json={"user_id": 1, "item": "Gizmo"}).get_json()
    resp = client.delete(f"/orders/{created['id']}")
    assert resp.status_code == 204
    assert client.get(f"/orders/{created['id']}").status_code == 404


def test_delete_order_not_found(client):
    resp = client.delete("/orders/9999")
    assert resp.status_code == 404


def test_create_order_with_in_process_users_service(tmp_path, monkeypatch):
    """End-to-end-ish test: a real users-service Flask app (its own test
    client, running in-process) backs the user-existence check instead of a
    live container or a hand-rolled mock.
    """
    users_db = str(tmp_path / "users.db")
    users_app = create_users_app(db_path=users_db)
    users_client = users_app.test_client()
    created_user = users_client.post(
        "/users", json={"name": "In Process Ann", "email": "ann@example.com"}
    ).get_json()

    def fake_get(url, timeout=5):
        # url looks like http://users-service:5001/users/<id>; forward the
        # path portion straight into the in-process users-service test client.
        path = "/" + url.split("/", 3)[3]
        return users_client.get(path)

    orders_db = str(tmp_path / "orders.db")
    orders_app = create_app(db_path=orders_db, users_service_url="http://users-service:5001")
    monkeypatch.setattr("orders_service.app.requests.get", fake_get)

    client = orders_app.test_client()
    resp = client.post(
        "/orders", json={"user_id": created_user["id"], "item": "Book", "quantity": 2}
    )
    assert resp.status_code == 201
    assert resp.get_json()["user_id"] == created_user["id"]


def test_create_order_with_in_process_users_service_rejects_missing_user(tmp_path, monkeypatch):
    users_db = str(tmp_path / "users2.db")
    users_app = create_users_app(db_path=users_db)
    users_client = users_app.test_client()

    def fake_get(url, timeout=5):
        path = "/" + url.split("/", 3)[3]
        return users_client.get(path)

    orders_db = str(tmp_path / "orders2.db")
    orders_app = create_app(db_path=orders_db, users_service_url="http://users-service:5001")
    monkeypatch.setattr("orders_service.app.requests.get", fake_get)

    client = orders_app.test_client()
    resp = client.post("/orders", json={"user_id": 42, "item": "Book"})
    assert resp.status_code == 404
