"""Deterministic J03 scenario variant generator.

``generate_operations(seed, contract_path)`` derives the complete operation
stream of one benchmark variant from nothing but the integer seed and the
frozen variant contract: document/version/route/decision/actor identities,
legal delivery order, deliberate duplicates, crash points, and deliberately
invalid schedules (late decisions, early registrar events, role reuse).
All randomness flows through :class:`random.Random` seeded with the seed
string (stable, hash-randomization independent), all output values are
integers and strings, and canonical output uses sorted keys — the same seed
therefore reproduces byte-identical streams on every supported runtime.

No operation carries a static public fixture id; every identity is derived
from the seeded generator.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = (REPO_ROOT / "process/bench/cases/J03-document-flow"
                    / "oracle/variant-contract.json")

CRASH_POINTS = ("after-commit-before-ack", "after-publish-before-sent")
INVALID_LABELS = ("late-decision", "registrar-early", "registrar-reject",
                  "actor-reuse", "closed-route")

STORYLINES = ("approve", "reject-expert", "supersede-before-partial",
              "supersede-after-partial", "registrar-early",
              "registrar-reject", "actor-reuse", "duplicate-decision")


def source_sha256() -> str:
    """SHA-256 of this generator module: the recorded generator identity."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def load_contract(contract_path: str | Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    return json.loads(Path(contract_path).read_text(encoding="utf-8"))


def corpus_seeds(contract_path: str | Path = DEFAULT_CONTRACT) -> list[int]:
    contract = load_contract(contract_path)
    corpus = contract["corpus"]
    return sorted(corpus["calibration_seeds"] + corpus["heldout_seeds"])


CORPUS_SEEDS = corpus_seeds()

GOLDEN_STREAM_SHA256: dict[int, str] = {
    1: "17a4cab125ac429b3769b6771dbaed545900d3e2096954906f117c6f7372e255",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def canonical_stream(operations: list[dict[str, Any]]) -> bytes:
    return _canonical(operations)


def stream_hash(operations: list[dict[str, Any]]) -> str:
    return hashlib.sha256(canonical_stream(operations)).hexdigest()


def _hex(rng: random.Random) -> str:
    return "%08x" % rng.getrandbits(32)


def _decision(rng: random.Random, route_id: str, document_id: str,
              version_id: str, actor_id: str, role: str, action: str, *,
              decision_id: str | None = None, valid: bool = True,
              label: str | None = None, expected_code: str | None = None,
              topic: str = "j03.workflow-events") -> dict[str, Any]:
    operation = {
        "kind": "decision", "op": "decision", "topic": topic,
        "route_id": route_id, "document_id": document_id,
        "version_id": version_id,
        "decision_id": decision_id or ("dec-" + _hex(rng)),
        "actor_id": actor_id, "role": role, "action": action,
        "valid": valid, "label": label, "expected_code": expected_code,
    }
    if not valid:
        assert label in INVALID_LABELS and expected_code, operation
    return operation


def _delivery(op: str, topic: str, event_id: str, **fields: Any) -> dict[str, Any]:
    return {"kind": "delivery", "op": op, "topic": topic,
            "event_id": event_id, **fields}


def _storyline(rng: random.Random, contract: dict[str, Any], index: int,
               storyline: str) -> list[dict[str, Any]]:
    document = "doc-" + _hex(rng)
    version_one = "ver-" + _hex(rng) + "-1"
    route_one = "rte-" + _hex(rng) + "-1"
    actors = {
        "legal": "act-" + _hex(rng) + "-legal",
        "security": "act-" + _hex(rng) + "-security",
        "registrar": "act-" + _hex(rng) + "-registrar",
    }
    topics = contract["topics"]
    stream: list[dict[str, Any]] = [
        {"kind": "http", "op": "create-document", "document_id": document,
         "title": "Generated variant document %d" % index},
        {"kind": "http", "op": "create-version", "document_id": document,
         "version_id": version_one, "content": "Generated body %d" % index},
        {"kind": "http", "op": "submit-version", "document_id": document,
         "version_id": version_one},
        _delivery("route-created", topics["document"], "evt-" + _hex(rng),
                  document_id=document, version_id=version_one,
                  route_id=route_one),
    ]

    def approve_all(route_id: str, version_id: str, legal: str | None = None,
                    security: str | None = None) -> list[dict[str, Any]]:
        legal_actor = legal or actors["legal"]
        security_actor = security or actors["security"]
        return [
            _decision(rng, route_id, document, version_id, legal_actor,
                      "legal", "APPROVE"),
            _delivery("decision-applied", topics["workflow"], "evt-" + _hex(rng),
                      document_id=document, route_id=route_id),
            _decision(rng, route_id, document, version_id, security_actor,
                      "security", "APPROVE"),
            _delivery("decision-applied", topics["workflow"], "evt-" + _hex(rng),
                      document_id=document, route_id=route_id),
            _decision(rng, route_id, document, version_id, actors["registrar"],
                      "registrar", "APPROVE"),
            _delivery("decision-applied", topics["workflow"], "evt-" + _hex(rng),
                      document_id=document, route_id=route_id),
        ]

    def supersede_to(route_one: str, previous_version: str) -> tuple[str, str, list[dict[str, Any]]]:
        version_two = "ver-" + _hex(rng) + "-2"
        route_two = "rte-" + _hex(rng) + "-2"
        handover = [
            {"kind": "http", "op": "create-version", "document_id": document,
             "version_id": version_two, "content": "Generated body %d rev 2" % index},
            {"kind": "http", "op": "submit-version", "document_id": document,
             "version_id": version_two},
            _delivery("route-superseded", topics["workflow"], "evt-" + _hex(rng),
                      document_id=document, version_id=previous_version,
                      route_id=route_one),
            _delivery("route-created", topics["document"], "evt-" + _hex(rng),
                      document_id=document, version_id=version_two,
                      route_id=route_two),
        ]
        return version_two, route_two, handover

    if storyline == "approve":
        stream.extend(approve_all(route_one, version_one))
    elif storyline == "reject-expert":
        stream.append(_decision(rng, route_one, document, version_one,
                                actors["legal"], "legal", "REJECT"))
        stream.append(_delivery("decision-applied", topics["workflow"],
                                "evt-" + _hex(rng), document_id=document,
                                route_id=route_one))
    elif storyline == "supersede-before-partial":
        version_two, route_two, handover = supersede_to(route_one, version_one)
        stream.extend(handover)
        stream.extend(approve_all(route_two, version_two))
        stream.append(_decision(rng, route_one, document, version_one,
                                actors["legal"], "legal", "REJECT",
                                valid=False, label="late-decision",
                                expected_code="IGNORED_LATE_DECISION"))
    elif storyline == "supersede-after-partial":
        stream.append(_decision(rng, route_one, document, version_one,
                                actors["legal"], "legal", "APPROVE"))
        stream.append(_delivery("decision-applied", topics["workflow"],
                                "evt-" + _hex(rng), document_id=document,
                                route_id=route_one))
        version_two, route_two, handover = supersede_to(route_one, version_one)
        stream.extend(handover)
        stream.extend(approve_all(route_two, version_two))
        stream.append(_decision(rng, route_one, document, version_one,
                                actors["security"], "security", "APPROVE",
                                valid=False, label="late-decision",
                                expected_code="IGNORED_LATE_DECISION"))
    elif storyline == "registrar-early":
        stream.append(_decision(rng, route_one, document, version_one,
                                actors["registrar"], "registrar", "APPROVE",
                                valid=False, label="registrar-early",
                                expected_code="EXPERT_REVIEW_INCOMPLETE"))
        stream.extend(approve_all(route_one, version_one))
    elif storyline == "registrar-reject":
        stream.append(_decision(rng, route_one, document, version_one,
                                actors["legal"], "legal", "APPROVE"))
        stream.append(_delivery("decision-applied", topics["workflow"],
                                "evt-" + _hex(rng), document_id=document,
                                route_id=route_one))
        stream.append(_decision(rng, route_one, document, version_one,
                                actors["registrar"], "registrar", "REJECT",
                                valid=False, label="registrar-reject",
                                expected_code="UNSUPPORTED_ACTION"))
        stream.append(_decision(rng, route_one, document, version_one,
                                actors["security"], "security", "APPROVE"))
        stream.append(_delivery("decision-applied", topics["workflow"],
                                "evt-" + _hex(rng), document_id=document,
                                route_id=route_one))
        stream.append(_decision(rng, route_one, document, version_one,
                                actors["registrar"], "registrar", "APPROVE"))
        stream.append(_delivery("decision-applied", topics["workflow"],
                                "evt-" + _hex(rng), document_id=document,
                                route_id=route_one))
    elif storyline == "actor-reuse":
        stream.append(_decision(rng, route_one, document, version_one,
                                actors["legal"], "legal", "APPROVE"))
        stream.append(_delivery("decision-applied", topics["workflow"],
                                "evt-" + _hex(rng), document_id=document,
                                route_id=route_one))
        stream.append(_decision(rng, route_one, document, version_one,
                                actors["legal"], "security", "APPROVE",
                                valid=False, label="actor-reuse",
                                expected_code="ACTOR_ROLE_MISMATCH"))
        stream.append(_decision(rng, route_one, document, version_one,
                                actors["security"], "security", "APPROVE"))
        stream.append(_delivery("decision-applied", topics["workflow"],
                                "evt-" + _hex(rng), document_id=document,
                                route_id=route_one))
        stream.append(_decision(rng, route_one, document, version_one,
                                actors["registrar"], "registrar", "APPROVE"))
        stream.append(_delivery("decision-applied", topics["workflow"],
                                "evt-" + _hex(rng), document_id=document,
                                route_id=route_one))
    elif storyline == "duplicate-decision":
        replayed = _decision(rng, route_one, document, version_one,
                             actors["legal"], "legal", "APPROVE",
                             decision_id="dec-" + _hex(rng))
        stream.append(dict(replayed))
        stream.append(_delivery("decision-applied", topics["workflow"],
                                "evt-" + _hex(rng), document_id=document,
                                route_id=route_one))
        stream.append({**replayed, "label": "duplicate-decision"})
    else:  # pragma: no cover - contract-validated above
        raise ValueError("unknown storyline: " + storyline)
    return stream


def generate_operations(seed: int,
                        contract_path: str | Path = DEFAULT_CONTRACT,
                        ) -> list[dict[str, Any]]:
    """Derive the complete, causally ordered operation stream of one variant."""
    contract = load_contract(contract_path)
    if seed < 0:
        raise ValueError("seed must be a non-negative integer")
    rng = random.Random("j03-variants-v1:%d" % seed)
    bounds = contract["documents"]
    document_count = rng.randint(bounds["min"], bounds["max"])
    storylines = list(contract["storylines"])

    streams = [
        _storyline(rng, contract, index,
                   storylines[rng.randrange(len(storylines))])
        for index in range(document_count)
    ]
    operations: list[dict[str, Any]] = []
    while any(streams):
        active = [position for position, stream in enumerate(streams) if stream]
        chosen = streams[active[rng.randrange(len(active))]]
        operations.append(chosen.pop(0))

    duplicate_min, duplicate_max = contract["delivery"]["duplicate_bounds"]
    delivery_positions = [position for position, operation in enumerate(operations)
                          if operation["kind"] == "delivery"]
    for _ in range(rng.randint(duplicate_min, duplicate_max)):
        if not delivery_positions:
            break
        position = delivery_positions[rng.randrange(len(delivery_positions))]
        original = operations[position]
        duplicate = {**original, "kind": "duplicate-delivery",
                     "valid": True, "label": "duplicate-delivery"}
        operations.insert(position + 1, duplicate)
        delivery_positions = [candidate + 1 if candidate > position else candidate
                              for candidate in delivery_positions]

    crash_min, crash_max = contract["delivery"]["crash_bounds"]
    for _ in range(rng.randint(crash_min, crash_max)):
        point = rng.choice(contract["delivery"]["crash_points"])
        service = rng.choice(contract["delivery"]["crash_services"])
        operations.insert(rng.randrange(len(operations) + 1),
                          {"kind": "crash", "point": point, "service": service})

    if not any(operation.get("valid") is False for operation in operations):
        anchor = next(operation for operation in operations
                      if operation["kind"] == "delivery"
                      and operation["op"] == "route-created")
        operations.append(_decision(
            rng, anchor["route_id"], anchor["document_id"],
            anchor["version_id"], "act-" + _hex(rng) + "-registrar",
            "registrar", "APPROVE", valid=False, label="closed-route",
            expected_code="IDENTITY_MISMATCH"))

    for index, operation in enumerate(operations):
        operation["index"] = index
        operation["operation_id"] = "op-%04d" % index
    return operations


def ambiguity_ids(operations: list[dict[str, Any]]) -> list[str]:
    return [operation["operation_id"] for operation in operations
            if operation.get("valid") is False]


def workload_ids(operations: list[dict[str, Any]]) -> list[str]:
    digest = stream_hash(operations)
    return ["workload-%s-bounded-load" % digest[:12]]


def variant_id(seed: int, operations: list[dict[str, Any]]) -> str:
    return "j03-v1-%010d-%s" % (seed, stream_hash(operations)[:12])


def build_manifest(seed: int,
                   contract_path: str | Path = DEFAULT_CONTRACT,
                   *,
                   source_revision: str,
                   generator_source_sha256: str | None = None) -> dict[str, Any]:
    """Build the schema-conformant variant manifest for one seed."""
    from scripts.document_flow.canonical import with_self_hash

    contract_path = Path(contract_path)
    operations = generate_operations(seed, contract_path)
    payload = canonical_stream(operations)
    stream_digest = hashlib.sha256(payload).hexdigest()
    identifier = variant_id(seed, operations)
    manifest = {
        "schema_version": 1,
        "variant_id": identifier,
        "seed": seed,
        "generator": {
            "source_revision": source_revision,
            "source_sha256": (generator_source_sha256
                              or source_sha256()),
            "contract_sha256": hashlib.sha256(
                contract_path.read_bytes()).hexdigest(),
        },
        "operation_stream": {
            "sha256": stream_digest,
            "operation_count": len(operations),
            "evidence_ref": {
                "key": "bench/runs/variants/%s/operations.json" % identifier,
                "sha256": stream_digest,
                "media_type": "application/json",
                "byte_length": len(payload),
                "producer_event_id": "generated-" + identifier,
            },
        },
        "ambiguity_ids": ambiguity_ids(operations),
        "workload_ids": workload_ids(operations),
    }
    return with_self_hash(manifest, "manifest_hash")


def manifest_hash(manifest: dict[str, Any]) -> str:
    from scripts.document_flow.canonical import content_hash

    return content_hash(manifest, exclude=("manifest_hash",))
