FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data

ENV PYTHONUNBUFFERED=1 \
    USERS_DB_PATH=/data/users.db

EXPOSE 5001

CMD ["gunicorn", "--bind", "0.0.0.0:5001", "wsgi:app"]
