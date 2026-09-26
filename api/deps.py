"""FastAPI dependencies: a Postgres connection per request, and the shared LLM client.

Reuses exactly the credentials the Python pipeline already uses locally (DATABASE_URL_DIRECT,
OPEN_ROUTER_API_KEY from .env) -- no new secrets to configure for local development. In the
target Cloud Run deployment (TECH_STACK.md Sec 4/6) these come from Secret Manager instead, but
the dependency contract here doesn't change either way.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg

from curator.llm.client import LLMClient


def get_db() -> Iterator[psycopg.Connection]:
    dsn = os.environ.get("DATABASE_URL_DIRECT")
    if not dsn:
        raise RuntimeError("DATABASE_URL_DIRECT is not set -- see .env.example")
    with psycopg.connect(dsn, autocommit=True) as conn:
        yield conn


def get_llm_client() -> LLMClient:
    return LLMClient()
