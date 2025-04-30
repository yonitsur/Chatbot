#!/bin/sh

python -m scripts.init_collection

uvicorn main:app --host ${UVICORN_HOST:-0.0.0.0} --port ${UVICORN_PORT:-8000}

