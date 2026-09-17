"""WSGI entrypoint used by gunicorn inside the container."""
import os

from orders_service.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5002)))
