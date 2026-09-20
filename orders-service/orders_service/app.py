"""orders-service: creates orders that reference a user_id.

Before creating an order, this service calls users-service over HTTP
(GET {USERS_SERVICE_URL}/users/<id>) to make sure the referenced user
actually exists. This is the classic "service-to-service call" in a
microservices demo.
"""
import os

import requests
from flask import Flask, jsonify, request

from .db import get_connection, init_db

DEFAULT_USERS_SERVICE_URL = os.environ.get(
    "USERS_SERVICE_URL", "http://users-service:5001"
)
DEFAULT_USERS_SERVICE_TIMEOUT = float(
    os.environ.get("USERS_SERVICE_TIMEOUT_SECONDS", "5")
)


def create_app(db_path=None, users_service_url=None, users_service_timeout=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or os.environ.get("ORDERS_DB_PATH", "orders.db")
    app.config["USERS_SERVICE_URL"] = users_service_url or DEFAULT_USERS_SERVICE_URL
    app.config["USERS_SERVICE_TIMEOUT"] = (
        users_service_timeout
        if users_service_timeout is not None
        else DEFAULT_USERS_SERVICE_TIMEOUT
    )
    init_db(app.config["DB_PATH"])

    def user_exists(user_id):
        """Return True/False if users-service answered, or None if unreachable."""
        base = app.config["USERS_SERVICE_URL"].rstrip("/")
        try:
            resp = requests.get(
                f"{base}/users/{user_id}", timeout=app.config["USERS_SERVICE_TIMEOUT"]
            )
        except requests.RequestException:
            return None
        if resp.status_code == 200:
            return True
        if resp.status_code == 404:
            return False
        return None

    @app.get("/health")
    def health():
        return jsonify(status="ok", service="orders-service"), 200

    @app.post("/orders")
    def create_order():
        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id")
        item = (data.get("item") or "").strip()
        quantity = data.get("quantity", 1)

        if not user_id or not item:
            return jsonify(error="user_id and item are required"), 400
        if not isinstance(user_id, int) or isinstance(user_id, bool):
            return jsonify(error="user_id must be an integer"), 400
        if not isinstance(quantity, int) or quantity < 1:
            return jsonify(error="quantity must be a positive integer"), 400

        exists = user_exists(user_id)
        if exists is None:
            return jsonify(error="could not verify user; users-service unavailable"), 502
        if not exists:
            return jsonify(error=f"user {user_id} does not exist"), 404

        conn = get_connection(app.config["DB_PATH"])
        cur = conn.execute(
            "INSERT INTO orders (user_id, item, quantity, status) VALUES (?, ?, ?, ?)",
            (user_id, item, quantity, "pending"),
        )
        conn.commit()
        order_id = cur.lastrowid
        conn.close()

        return (
            jsonify(id=order_id, user_id=user_id, item=item, quantity=quantity, status="pending"),
            201,
        )

    @app.get("/orders")
    def list_orders():
        conn = get_connection(app.config["DB_PATH"])
        rows = conn.execute(
            "SELECT id, user_id, item, quantity, status FROM orders ORDER BY id"
        ).fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows]), 200

    @app.get("/orders/<int:order_id>")
    def get_order(order_id):
        conn = get_connection(app.config["DB_PATH"])
        row = conn.execute(
            "SELECT id, user_id, item, quantity, status FROM orders WHERE id = ?",
            (order_id,),
        ).fetchone()
        conn.close()
        if row is None:
            return jsonify(error="order not found"), 404
        return jsonify(dict(row)), 200

    @app.delete("/orders/<int:order_id>")
    def delete_order(order_id):
        conn = get_connection(app.config["DB_PATH"])
        row = conn.execute("SELECT id FROM orders WHERE id = ?", (order_id,)).fetchone()
        if row is None:
            conn.close()
            return jsonify(error="order not found"), 404
        conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()
        return "", 204

    return app


if __name__ == "__main__":
    flask_app = create_app()
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5002)))
