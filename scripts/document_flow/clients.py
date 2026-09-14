"""Judge-owned clients restricted to public surfaces and read-only SQL."""

from __future__ import annotations

import json
import re
from typing import Any, Callable
from urllib import request


class ClientError(RuntimeError):
    pass


class UnsafeObservation(ValueError):
    pass


class HttpClient:
    def __init__(self, base_url: str, opener: Callable[..., Any] = request.urlopen):
        self.base_url = base_url.rstrip("/")
        self._opener = opener

    def json(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        if not path.startswith("/") or ".." in path:
            raise ClientError("HTTP path must be an absolute public endpoint")
        data = None if body is None else json.dumps(body, separators=(",", ":")).encode()
        call = request.Request(self.base_url + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
        with self._opener(call, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))


class KafkaClient:
    """Invokes a pinned container-side Kafka CLI without shell expansion."""

    def __init__(self, executor, broker_container: str):
        self._executor = executor
        self._container = broker_container

    def consume(self, topic: str, *, max_messages: int = 100):
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", topic):
            raise ClientError("unsafe Kafka topic")
        argv = ["docker", "exec", self._container, "/opt/kafka/bin/kafka-console-consumer.sh",
                "--bootstrap-server", "localhost:9092", "--topic", topic,
                "--from-beginning", "--max-messages", str(max_messages), "--timeout-ms", "10000"]
        return self._executor(argv, cwd=".", timeout=20)


class ReadOnlySqlClient:
    TABLES = frozenset({"document", "document_version", "route", "decision",
                        "outbox_event", "inbox_event", "audit_event"})
    FORBIDDEN = re.compile(
        r"\b(insert|update|delete|merge|alter|drop|create|truncate|grant|revoke|copy|call|do|execute|vacuum|analyze)\b",
        re.IGNORECASE)

    def __init__(self, executor, postgres_container: str, database: str, user: str):
        self._executor = executor
        self._container = postgres_container
        self._database = database
        self._user = user

    def query(self, sql: str) -> list[dict[str, Any]]:
        normalized = sql.strip()
        if (not normalized.lower().startswith("select ") or ";" in normalized
                or "--" in normalized or "/*" in normalized
                or self.FORBIDDEN.search(normalized)
                or re.search(r"\b(pg_sleep|dblink|lo_import|lo_export)\s*\(", normalized, re.I)):
            raise UnsafeObservation("only one allow-listed SELECT is permitted")
        tables = {match.lower() for match in re.findall(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_]*)", normalized, re.I)}
        if not tables or not tables <= self.TABLES:
            raise UnsafeObservation("SQL table is outside the judge observation allow-list")
        wrapped = ("BEGIN READ ONLY; SELECT COALESCE(json_agg(row_to_json(j03_observation)), "
                   "'[]'::json) FROM (" + normalized + ") AS j03_observation; COMMIT;")
        argv = ["docker", "exec", self._container, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1",
                "-U", self._user, "-d", self._database, "-At", "-c", wrapped]
        result = self._executor(argv, cwd=".", timeout=15)
        if result.exit_code != 0:
            raise ClientError("judge database observation failed")
        text = result.stdout.strip()
        return [] if not text else json.loads(text)
