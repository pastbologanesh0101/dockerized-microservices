FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data

ENV PYTHONUNBUFFERED=1 \
    ORDERS_DB_PATH=/data/orders.db \
    USERS_SERVICE_URL=http://users-service:5001

EXPOSE 5002

CMD ["gunicorn", "--bind", "0.0.0.0:5002", "wsgi:app"]
