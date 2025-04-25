FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1

ENV PYTHONUNBUFFERED 1

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD uvicorn main:app --host ${UVICORN_HOST:-0.0.0.0} --port ${UVICORN_PORT:-8000}
#CMD ["uvicorn", "main:app", "--host", "${UVICORN_HOST:-0.0.0.0}", "--port", "${UVICORN_PORT:-8000}"]
#CMD ["uvicorn", "main:app"]