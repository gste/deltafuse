"""Public HTTP and Kafka smoke clients for the J03 baseline stack.

Standard library only. HTTP endpoints are the loopback ports published by
the pinned compose stack; Kafka is observed from inside the run-owned
private network through the digest-pinned Kafka image's console consumer,
so no broker port is ever exposed to the host.
"""

import json
import subprocess
import time
import urllib.error
import urllib.request

# Tools image for in-network topic observation (the native broker image
# ships no CLI). Pulled and digest-pinned during provisioning.
KAFKA_TOOLS_IMAGE = ("apache/kafka@sha256:4ceccc577f03f51f6af8dbfda55194d0d892f4"
                     "fa7913ffbded567ce3895622ed")

# Exit contract (CONTRACTS.md): 0 pass, 1 valid failure, 2 invocation
# error, 3 infrastructure failure.
EXIT_PASS = 0
EXIT_VALID_FAILURE = 1
EXIT_INVOCATION = 2
EXIT_INFRASTRUCTURE = 3


class PublicFailure(Exception):
    """A named public assertion failed against a reachable stack."""

    def __init__(self, assertion_id, detail):
        super().__init__("%s: %s" % (assertion_id, detail))
        self.assertion_id = assertion_id
        self.detail = detail


class InfrastructureFailure(Exception):
    """The stack is unreachable or unhealthy; nothing is scored."""

    def __init__(self, detail):
        super().__init__("J03-PUB-INF-001: %s" % (detail,))


def request_json(base_url, method, path, body=None, timeout=10):
    url = base_url.rstrip("/") + path
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        payload = error.read().decode("utf-8")
        try:
            return error.code, json.loads(payload)
        except ValueError:
            return error.code, {"raw": payload}
    except (urllib.error.URLError, OSError) as error:
        raise InfrastructureFailure("%s %s failed: %s" % (method, url, error))


def get_flow(document_url, document_id):
    status, body = request_json(document_url, "GET",
                                "/api/documents/%s/flow" % document_id)
    if status != 200:
        raise PublicFailure("J03-PUB-004",
                            "canonical observation for %s returned %s: %s"
                            % (document_id, status, body))
    return body


def converged(observation):
    watermark = observation["watermark"]
    return bool(watermark["caught_up"]) and all(
        watermark[name] >= watermark["required_sequence"]
        for name in ("document_sequence", "workflow_sequence", "audit_sequence")
    )


def wait_for_flow(document_url, document_id, predicate, deadline_seconds,
                  assertion_id):
    """Poll the canonical observation until predicate holds or time runs out."""
    deadline = time.monotonic() + deadline_seconds
    last = None
    while time.monotonic() < deadline:
        last = get_flow(document_url, document_id)
        if converged(last) and predicate(last):
            return last
        time.sleep(0.5)
    raise PublicFailure(assertion_id,
                        "canonical observation never satisfied %s; last=%s"
                        % (assertion_id, json.dumps(last, sort_keys=True)))


def kafka_events(private_network, topic, timeout_ms=8000):
    """Consume an entire topic from inside the run-owned private network."""
    command = [
        "docker", "run", "--rm", "--network", private_network,
        KAFKA_TOOLS_IMAGE, "/opt/kafka/bin/kafka-console-consumer.sh",
        "--bootstrap-server", "kafka:9092", "--topic", topic,
        "--from-beginning", "--timeout-ms", str(timeout_ms),
    ]
    finished = subprocess.run(command, capture_output=True, text=True,
                              timeout=timeout_ms / 1000.0 + 60)
    events = []
    for line in finished.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    return events
