# Reproducible container so the Cloud Run revision starts reliably.
# A revision whose container fails to start serves every request as a
# 503 "Service Unavailable" (which Make reports as ConnectionError).
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# functions-framework launches gunicorn in production mode and binds to $PORT,
# which Cloud Run provides (default 8080).
ENV PORT=8080
CMD exec functions-framework --target=hello_http --host=0.0.0.0 --port=${PORT}
