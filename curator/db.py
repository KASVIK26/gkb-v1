"""Neo4j database connection and query management for AgriHub KB."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from neo4j import AsyncDriver, GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable


def load_env_file(env_path: str | Path | None = None) -> None:
    """Load environment variables from .env file."""
    if env_path is None:
        env_path = Path(__file__).resolve().parents[1] / ".env"
    
    env_path = Path(env_path)
    if not env_path.exists():
        return
    
    with env_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()


class DBConfig:
    """Database configuration from environment variables."""

    def __init__(self):
        # Load .env file first if it exists
        load_env_file()
        
        self.uri = os.getenv("NEO4J_URI", "").strip()
        self.user = os.getenv("NEO4J_USER", "").strip()
        self.password = os.getenv("NEO4J_PASSWORD", "").strip()

    def validate(self) -> None:
        """Raise ValueError if any required credential is missing."""
        if not self.uri:
            raise ValueError("NEO4J_URI is not set in .env")
        if not self.user:
            raise ValueError("NEO4J_USER is not set in .env")
        if not self.password:
            raise ValueError("NEO4J_PASSWORD is not set in .env")


class DBDriver:
    """Wrapper for Neo4j driver with connection pooling and session management."""

    def __init__(self, config: DBConfig | None = None):
        if config is None:
            config = DBConfig()
        
        config.validate()
        self.config = config
        self._driver = None

    def connect(self) -> None:
        """Establish connection to Neo4j AuraDB."""
        try:
            self._driver = GraphDatabase.driver(
                self.config.uri,
                auth=(self.config.user, self.config.password),
            )
            # Verify connection
            with self._driver.session() as session:
                result = session.run("RETURN 1")
                result.single()
            print(f"✓ Connected to Neo4j at {self.config.uri}")
        except AuthError as e:
            raise ValueError(f"Neo4j authentication failed: {e}") from e
        except ServiceUnavailable as e:
            raise ConnectionError(f"Neo4j service unavailable at {self.config.uri}: {e}") from e

    def close(self) -> None:
        """Close the driver and release resources."""
        if self._driver:
            self._driver.close()
            self._driver = None
            print("✓ Closed Neo4j connection")

    @contextmanager
    def session(self):
        """Context manager for Neo4j sessions."""
        if not self._driver:
            raise RuntimeError("Driver not connected. Call .connect() first.")
        session = self._driver.session()
        try:
            yield session
        finally:
            session.close()

    def run(self, query: str, **kwargs) -> list:
        """Run a read/write query and return results."""
        with self.session() as session:
            result = session.run(query, **kwargs)
            return [record for record in result]

    def verify_connection(self) -> bool:
        """Check if the driver is connected and the database is reachable."""
        if not self._driver:
            return False
        try:
            with self._driver.session() as session:
                session.run("RETURN 1").single()
            return True
        except Exception:
            return False
