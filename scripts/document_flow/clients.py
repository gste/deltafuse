"""Judge-owned clients restricted to public surfaces and read-only SQL."""

from __future__ import annotations

import json
import base64
import re
import os
from pathlib import Path
import shutil
import tempfile
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
    """Uses Kafka client jars already present in a run-owned service container."""

    _SOURCE = r'''import java.time.Duration;
import java.util.List;
import java.util.Properties;
import java.util.UUID;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;

class J03KafkaProbe {
  public static void main(String[] a) throws Exception {
    System.setProperty("org.slf4j.simpleLogger.defaultLogLevel", "warn");
    if (a.length < 3) throw new IllegalArgumentException("mode bootstrap topic required");
    if ("publish".equals(a[0])) {
      Properties p = new Properties();
      p.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, a[1]);
      p.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
      p.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
      p.put(ProducerConfig.ACKS_CONFIG, "all");
      try (KafkaProducer<String,String> producer = new KafkaProducer<>(p)) {
        producer.send(new ProducerRecord<>(a[2], a[3], a[4])).get();
      }
      return;
    }
    Properties p = new Properties();
    p.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, a[1]);
    p.put(ConsumerConfig.GROUP_ID_CONFIG, "j03-judge-" + UUID.randomUUID());
    p.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
    p.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, "false");
    p.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
    p.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
    int maximum = Integer.parseInt(a[3]);
    long deadline = System.nanoTime() + Duration.ofMillis(Long.parseLong(a[4])).toNanos();
    int seen = 0;
    try (KafkaConsumer<String,String> consumer = new KafkaConsumer<>(p)) {
      consumer.subscribe(List.of(a[2]));
      while (seen < maximum && System.nanoTime() < deadline) {
        for (var record : consumer.poll(Duration.ofMillis(250))) {
          System.out.println(record.value());
          if (++seen >= maximum) break;
        }
      }
    }
  }
}'''

    def __init__(self, executor, broker_container: str):
        self._executor = executor
        self._container = broker_container

    def _client_container(self):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,127}", self._container):
            raise ClientError("unsafe Kafka container")
        marker = "-kafka-"
        if marker not in self._container:
            raise ClientError("broker container does not identify its run")
        project, _, suffix = self._container.rpartition(marker)
        return project + "-workflow-service-" + suffix

    def _java(self, arguments, *, timeout):
        container = self._client_container()
        encoded = base64.b64encode(self._compiled_probe()).decode("ascii")
        copied = self._executor(
            ["docker", "exec", container, "sh", "-c",
             'printf "%s" "$1" | base64 -d > /tmp/J03KafkaProbe.class', "j03", encoded],
            cwd=".", timeout=15)
        if copied.exit_code != 0:
            return copied
        return self._executor(
            ["docker", "exec", container, "java", "--class-path", "/tmp:/app/lib/*",
             "J03KafkaProbe", *arguments], cwd=".", timeout=timeout)

    def _compiled_probe(self):
        repository = os.environ.get("J03_MAVEN_REPOSITORY")
        jars = [] if not repository else sorted(
            Path(repository).glob("org/apache/kafka/kafka-clients/*/kafka-clients-*.jar"))
        javac = (str(Path(os.environ["JAVA_HOME"]) / "bin" / "javac.exe")
                 if os.environ.get("JAVA_HOME") else (shutil.which("javac") or "javac"))
        if not jars:
            raise ClientError("pinned Kafka client jar is unavailable")
        with tempfile.TemporaryDirectory(prefix="j03-kafka-compile-") as directory:
            source = Path(directory) / "J03KafkaProbe.java"
            source.write_text(self._SOURCE, encoding="utf-8")
            compiled = self._executor([javac, "-cp", str(jars[-1]), str(source)],
                                      cwd=directory, timeout=30)
            if compiled.exit_code != 0:
                raise ClientError("judge Kafka probe compilation failed: " + compiled.stderr)
            return (Path(directory) / "J03KafkaProbe.class").read_bytes()

    def publish(self, topic: str, key: str, value: str):
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", topic):
            raise ClientError("unsafe Kafka topic")
        if not isinstance(key, str) or not isinstance(value, str):
            raise ClientError("Kafka key and value must be strings")
        return self._java(["publish", "kafka:9092", topic, key, value], timeout=30)

    def consume(self, topic: str, *, max_messages: int = 100):
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", topic):
            raise ClientError("unsafe Kafka topic")
        if not isinstance(max_messages, int) or not 1 <= max_messages <= 1000:
            raise ClientError("max_messages is outside the judge bound")
        return self._java(["consume", "kafka:9092", topic, str(max_messages), "10000"],
                          timeout=30)


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
