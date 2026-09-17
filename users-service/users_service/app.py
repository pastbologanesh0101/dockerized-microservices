"""users-service: a small Flask CRUD API backed by SQLite.

Responsible for owning user records. Other services (orders-service via the
api-gateway-service, or directly) call this service over HTTP to look up or
validate users.
"""
import os
import sqlite3

from flask import Flask, jsonify, request

from .db import get_connection, init_db


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or os.environ.get("USERS_DB_PATH", "users.db")
    init_db(app.config["DB_PATH"])

    @app.get("/health")
    def health():
        return jsonify(status="ok", service="users-service"), 200

    @app.post("/users")
    def create_user():
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()
        if not name or not email:
            return jsonify(error="name and email are required"), 400

        conn = get_connection(app.config["DB_PATH"])
        try:
            cur = conn.execute(
                "INSERT INTO users (name, email) VALUES (?, ?)", (name, email)
            )
            conn.commit()
            user_id = cur.lastrowid
        except sqlite3.IntegrityError:
            return jsonify(error="a user with that email already exists"), 409
        finally:
            conn.close()

        return jsonify(id=user_id, name=name, email=email), 201

    @app.get("/users")
    def list_users():
        conn = get_connection(app.config["DB_PATH"])
        rows = conn.execute("SELECT id, name, email FROM users ORDER BY id").fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows]), 200

    @app.get("/users/<int:user_id>")
    def get_user(user_id):
        conn = get_connection(app.config["DB_PATH"])
        row = conn.execute(
            "SELECT id, name, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        conn.close()
        if row is None:
            return jsonify(error="user not found"), 404
        return jsonify(dict(row)), 200

    @app.put("/users/<int:user_id>")
    def update_user(user_id):
        data = request.get_json(silent=True) or {}
        conn = get_connection(app.config["DB_PATH"])
        current = conn.execute(
            "SELECT id, name, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if current is None:
            conn.close()
            return jsonify(error="user not found"), 404

        new_name = (data.get("name") or current["name"]).strip()
        new_email = (data.get("email") or current["email"]).strip()
        try:
            conn.execute(
                "UPDATE users SET name = ?, email = ? WHERE id = ?",
                (new_name, new_email, user_id),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify(error="a user with that email already exists"), 409
        conn.close()
        return jsonify(id=user_id, name=new_name, email=new_email), 200

    @app.delete("/users/<int:user_id>")
    def delete_user(user_id):
        conn = get_connection(app.config["DB_PATH"])
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            conn.close()
            return jsonify(error="user not found"), 404
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return "", 204

    return app


if __name__ == "__main__":
    flask_app = create_app()
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
