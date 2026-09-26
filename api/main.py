"""FastAPI app: the paper-extraction review pipeline's HTTP surface.

Run locally: uvicorn api.main:app --reload
Needs DATABASE_URL_DIRECT and OPEN_ROUTER_API_KEY in .env (same as the Python CLI already uses).
Deployment target (not done by this session): Cloud Run, per TECH_STACK.md Sec 4/6 -- see Dockerfile.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import lit

app = FastAPI(title="AgriHub GKB paper-extraction API", version="0.1.0")

_allowed_origins = [
    origin.strip()
    for origin in os.environ.get(
        "API_CORS_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501,http://localhost:8788"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(lit.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
