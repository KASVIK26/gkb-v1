"""Shared fixtures.

Database tests need PostgreSQL with pg_trgm:
  * TEST_DATABASE_URL set  -> use that server (CI service container, `supabase start`, ...)
  * else local binaries    -> start a throwaway cluster in a temp dir (never touches your servers)
  * else                   -> skip (or fail when REQUIRE_DB_TESTS is set, as in CI)
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

_WINDOWS_PG_VERSIONS = ("17", "16", "15", "18")  # prefer Supabase's current major


def _pg_bindir() -> Path | None:
    for version in _WINDOWS_PG_VERSIONS:
        candidate = Path(rf"C:\Program Files\PostgreSQL\{version}\bin")
        if (candidate / "pg_ctl.exe").exists():
            return candidate
    found = shutil.which("pg_ctl")
    return Path(found).parent if found else None


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def pg_dsn(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        yield url
        return

    bindir = _pg_bindir()
    if bindir is None:
        message = "no PostgreSQL binaries found; set TEST_DATABASE_URL to run database tests"
        if os.environ.get("REQUIRE_DB_TESTS"):
            pytest.fail(message)
        pytest.skip(message)

    data_dir = tmp_path_factory.mktemp("pgdata")
    subprocess.run(
        [str(bindir / "initdb"), "-D", str(data_dir), "-U", "postgres", "--auth=trust", "--encoding=UTF8",
         "--no-locale"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    port = _free_port()
    pg_ctl = str(bindir / "pg_ctl")
    # Output goes to a log file: pg_ctl's child process would otherwise hold captured pipes open.
    subprocess.run(
        [pg_ctl, "-D", str(data_dir), "-l", str(data_dir / "server.log"), "-w",
         "-o", f"-p {port} -c listen_addresses=127.0.0.1", "start"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        yield f"postgresql://postgres@127.0.0.1:{port}/postgres"
    finally:
        subprocess.run([pg_ctl, "-D", str(data_dir), "-m", "fast", "-w", "stop"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@pytest.fixture()
def pg_conn(pg_dsn: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS extensions")
        conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm SCHEMA extensions")
        yield conn


@pytest.fixture()
def release_schema(pg_conn: psycopg.Connection) -> Iterator[str]:
    """A unique, empty-named release schema that is dropped after the test."""
    schema = f"kg_test_{uuid.uuid4().hex[:10]}"
    try:
        yield schema
    finally:
        pg_conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
