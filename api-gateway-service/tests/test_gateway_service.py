import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from gateway_service.app import create_app


class FakeUpstreamResponse:
    def __init__(self, status_code, json_body=None, content_type="application/json"):
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.content = json.dumps(json_body if json_body is not None else {}).encode()


@pytest.fixture
def client():
    app = create_app(
        users_service_url="http://users-service:5001",
        orders_service_url="http://orders-service:5002",
    )
    app.testing = True
    with app.test_client() as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["service"] == "api-gateway-service"


@patch("gateway_service.app.requests.request")
def test_users_get_list_proxies_to_users_service(mock_request, client):
    mock_request.return_value = FakeUpstreamResponse(200, [{"id": 1, "name": "Ada"}])
    resp = client.get("/users")
    assert resp.status_code == 200
    assert resp.get_json() == [{"id": 1, "name": "Ada"}]
    called_kwargs = mock_request.call_args.kwargs
    assert called_kwargs["method"] == "GET"
    assert called_kwargs["url"] == "http://users-service:5001/users"


@patch("gateway_service.app.requests.request")
def test_users_get_single_proxies_with_subpath(mock_request, client):
    mock_request.return_value = FakeUpstreamResponse(200, {"id": 7, "name": "Bob"})
    resp = client.get("/users/7")
    assert resp.status_code == 200
    assert resp.get_json()["id"] == 7
    called_kwargs = mock_request.call_args.kwargs
    assert called_kwargs["url"] == "http://users-service:5001/users/7"


@patch("gateway_service.app.requests.request")
def test_users_post_forwards_json_body(mock_request, client):
    mock_request.return_value = FakeUpstreamResponse(201, {"id": 1, "name": "New"})
    resp = client.post("/users", json={"name": "New", "email": "new@example.com"})
    assert resp.status_code == 201
    called_kwargs = mock_request.call_args.kwargs
    assert called_kwargs["method"] == "POST"
    assert called_kwargs["json"] == {"name": "New", "email": "new@example.com"}


@patch("gateway_service.app.requests.request")
def test_orders_get_list_proxies_to_orders_service(mock_request, client):
    mock_request.return_value = FakeUpstreamResponse(200, [{"id": 1, "item": "Widget"}])
    resp = client.get("/orders")
    assert resp.status_code == 200
    called_kwargs = mock_request.call_args.kwargs
    assert called_kwargs["url"] == "http://orders-service:5002/orders"


@patch("gateway_service.app.requests.request")
def test_orders_post_forwards_json_body(mock_request, client):
    mock_request.return_value = FakeUpstreamResponse(201, {"id": 1, "user_id": 1, "item": "Widget"})
    resp = client.post("/orders", json={"user_id": 1, "item": "Widget"})
    assert resp.status_code == 201
    called_kwargs = mock_request.call_args.kwargs
    assert called_kwargs["url"] == "http://orders-service:5002/orders"
    assert called_kwargs["json"] == {"user_id": 1, "item": "Widget"}


@patch("gateway_service.app.requests.request")
def test_orders_delete_proxies_with_subpath_and_method(mock_request, client):
    mock_request.return_value = FakeUpstreamResponse(204, {})
    resp = client.delete("/orders/3")
    assert resp.status_code == 204
    called_kwargs = mock_request.call_args.kwargs
    assert called_kwargs["method"] == "DELETE"
    assert called_kwargs["url"] == "http://orders-service:5002/orders/3"


@patch("gateway_service.app.requests.request")
def test_upstream_error_propagates_status_code(mock_request, client):
    mock_request.return_value = FakeUpstreamResponse(404, {"error": "user not found"})
    resp = client.get("/users/999")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "user not found"


@patch("gateway_service.app.requests.request")
def test_upstream_unreachable_returns_502(mock_request, client):
    import requests

    mock_request.side_effect = requests.ConnectionError("connection refused")
    resp = client.get("/users")
    assert resp.status_code == 502
    assert "unavailable" in resp.get_json()["error"]
