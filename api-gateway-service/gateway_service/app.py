"""api-gateway-service: a thin reverse proxy in front of users-service and
orders-service.

Routes:
  /users*  -> USERS_SERVICE_URL
  /orders* -> ORDERS_SERVICE_URL

This is deliberately small and written fresh for this project: it forwards
method, query string, and JSON body, and relays the upstream status code,
JSON/plain body, and content type back to the caller.
"""
import os

import requests
from flask import Flask, Response, jsonify, request

DEFAULT_USERS_SERVICE_URL = os.environ.get("USERS_SERVICE_URL", "http://users-service:5001")
DEFAULT_ORDERS_SERVICE_URL = os.environ.get("ORDERS_SERVICE_URL", "http://orders-service:5002")

# Headers that must not be blindly copied from the upstream response.
_EXCLUDED_RESPONSE_HEADERS = {
    "content-encoding",
    "content-length",
    "transfer-encoding",
    "connection",
}


def create_app(users_service_url=None, orders_service_url=None):
    app = Flask(__name__)
    app.config["USERS_SERVICE_URL"] = (users_service_url or DEFAULT_USERS_SERVICE_URL).rstrip("/")
    app.config["ORDERS_SERVICE_URL"] = (orders_service_url or DEFAULT_ORDERS_SERVICE_URL).rstrip("/")

    @app.get("/health")
    def health():
        return jsonify(status="ok", service="api-gateway-service"), 200

    def proxy(base_url, prefix, subpath):
        target = f"{base_url}/{prefix}"
        if subpath:
            target = f"{target}/{subpath}"

        try:
            upstream = requests.request(
                method=request.method,
                url=target,
                params=request.args,
                json=request.get_json(silent=True),
                timeout=5,
            )
        except requests.RequestException as exc:
            return jsonify(error=f"upstream '{prefix}' service unavailable: {exc}"), 502

        headers = [
            (key, value)
            for key, value in upstream.headers.items()
            if key.lower() not in _EXCLUDED_RESPONSE_HEADERS
        ]
        return Response(
            upstream.content,
            status=upstream.status_code,
            headers=headers,
            content_type=upstream.headers.get("Content-Type"),
        )

    @app.route("/users", defaults={"subpath": ""}, methods=["GET", "POST", "PUT", "DELETE"])
    @app.route("/users/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE"])
    def users_proxy(subpath):
        return proxy(app.config["USERS_SERVICE_URL"], "users", subpath)

    @app.route("/orders", defaults={"subpath": ""}, methods=["GET", "POST", "PUT", "DELETE"])
    @app.route("/orders/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE"])
    def orders_proxy(subpath):
        return proxy(app.config["ORDERS_SERVICE_URL"], "orders", subpath)

    return app


if __name__ == "__main__":
    flask_app = create_app()
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
