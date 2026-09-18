# Change Idea: Schema-Driven Artifact Writer for DeltaFuse

## Problem

DeltaFuse Workers, especially smaller local language models, frequently fail on mechanical serialization details when creating intermediate framework artifacts. Typical failures include invalid YAML indentation, malformed frontmatter, incorrect quoting, broken multiline strings, missing required fields, unknown keys, and accidental rewriting of unrelated fields.

These failures do not necessarily indicate incorrect reasoning or poor artifact content. They often reflect the difficulty of producing syntax-perfect YAML while simultaneously reasoning about product requirements, evidence, lifecycle state, and provenance.

As a result, mechanically invalid artifacts can block otherwise valid work, consume retries, and obscure the distinction between semantic failure and serialization failure.

## Proposed Change

Introduce a schema-driven `Artifact Writer` capability that converts typed structured payloads into canonical DeltaFuse artifacts.

The Worker remains responsible for semantic content. The Artifact Writer is responsible for serialization, schema conformance, mechanical metadata, safe updates, and atomic persistence.

The intended boundary is:

```text
Worker owns:
- intent
- claims
- decisions
- requirement and task content
- narrative prose
- evidence references selected from available evidence

Artifact Writer owns:
- YAML syntax and canonical formatting
- schema validation
- required mechanical fields
- deterministic key ordering
- safe multiline serialization
- atomic file writes
- parse-and-validate round trips
- preservation of unrelated fields during updates

Core owns:
- authorization
- lifecycle transitions
- Human Gates
- evidence binding rules
- source and snapshot identity
- enforcement of process invariants
```

The Artifact Writer is not another Worker and must not make product decisions.

## Preferred Interaction Model

Instead of asking a Worker to emit complete YAML, provide typed operations such as:

```text
artifact.create(kind, payload)
artifact.update(path, patch)
artifact.validate(path)
```

Example Worker payload:

```json
{
  "artifact_type": "requirement_delta",
  "requirements": [
    {
      "id": "REQ-001",
      "statement": "A superseded route must reject late decisions."
    }
  ]
}
```

The Artifact Writer would:

1. Validate the payload against the schema for the selected artifact type.
2. Reject missing, unknown, or incorrectly typed semantic fields.
3. Add only contract-defined mechanical metadata.
4. Serialize the payload into canonical YAML or YAML frontmatter.
5. Write through a temporary file and atomically replace the target.
6. Parse the written artifact again.
7. Revalidate it against the same schema.
8. Return a structured receipt containing the target path, schema identity, content hash, and validation result.

## Create, Update, and Validate Operations

### Create

`artifact.create` creates a new artifact from a complete typed payload.

It must reject an existing target unless the caller explicitly uses an authorized replacement operation.

### Update

`artifact.update` applies a typed patch to selected semantic fields without requiring the Worker to reproduce the entire file.

For example:

```json
{
  "status": "verified",
  "evidence_refs": ["EV-014"]
}
```

The writer must preserve unknown-to-the-patch but schema-valid fields, prevent unauthorized lifecycle changes, and validate the complete resulting artifact.

This operation is particularly important for smaller models because it avoids full-file YAML rewrites.

### Validate

`artifact.validate` performs parsing, schema validation, semantic invariant checks, and identity verification without modifying the artifact.

It should return actionable, field-specific diagnostics rather than raw parser exceptions.

## Fail-Closed Behavior

The writer must never repair semantic content heuristically.

If a required field is missing, an enum value is invalid, or a reference cannot be resolved, it must return a structured error. It must not silently invent values, rename suspicious fields, infer lifecycle states, or remove unknown content to make validation pass.

Automatic generation should be limited to deterministic mechanical values, such as:

- schema version;
- canonical formatting;
- calculated content hashes;
- timestamps when the contract requires them;
- source identity already supplied or resolved by Core;
- stable IDs only when their generation algorithm is explicitly specified.

Human Gate decisions, verification status, evidence conclusions, and product requirements must never be inferred by the writer.

## Artifact Format Guidance

Use YAML only for compact structured metadata.

For artifacts containing substantial prose, prefer:

```text
artifact.md
  YAML frontmatter — generated and validated by the Artifact Writer
  Markdown body    — authored by the Worker
```

Alternatively, store narrative content in a separate Markdown file and use YAML as a small typed index containing identifiers, relationships, state, and provenance.

The Worker should not be required to escape large prose blocks inside YAML unless the artifact contract genuinely requires it.

## Structured Output and Model Compatibility

The Worker-facing payload should use a small schema tailored to the current artifact type and lifecycle operation. Avoid exposing a single large universal schema.

Where supported, use constrained structured output or tool-call argument validation. This does not eliminate semantic validation, but it significantly reduces syntax failures for smaller models.

Validation errors should be returned in a compact form suitable for one targeted retry:

```json
{
  "ok": false,
  "errors": [
    {
      "path": "requirements[0].id",
      "code": "required",
      "message": "A stable requirement ID is required."
    }
  ]
}
```

## Provenance and Evidence

Every write receipt should record:

- operation type;
- artifact type and schema version;
- target path;
- input payload hash;
- previous artifact hash for updates;
- resulting artifact hash;
- validation result;
- fields generated mechanically by the writer;
- source or snapshot identity where applicable.

The original structured payload and the generated artifact must remain distinguishable. Successful serialization proves only structural validity; it does not prove that the artifact is semantically correct, verified, or qualified.

## Integration Requirements

The change should preserve the existing DeltaFuse separation between Core and Worker:

- Skills instruct the Worker when and how to request artifact operations.
- The Artifact Writer performs deterministic transformation and validation.
- Core authorizes paths and lifecycle operations and evaluates gates.
- Schemas remain the authoritative structural contracts.
- Human Gates remain human.
- Evidence validation remains independent from file serialization.

Generated local skill snapshots and templates must be updated together with canonical documentation, schemas, validators, installers, and tests when the artifact contract changes.

## Initial Scope

Start with artifact types that currently suffer most from mechanical YAML failures:

1. YAML frontmatter for Change artifacts.
2. Verification evidence such as `evidence/verification/run.yaml`.
3. Task and requirement indexes.
4. Lifecycle status updates that modify only a few fields.

Do not initially attempt to convert all DeltaFuse documents into generated YAML.

## Acceptance Criteria

The change is successful when:

- a Worker can create supported artifacts without emitting raw YAML;
- malformed structured payloads fail before any file is changed;
- supported artifacts are serialized deterministically;
- every write is followed by parse and schema validation;
- updates preserve unrelated fields;
- unauthorized lifecycle or Human Gate changes are rejected;
- semantic omissions are not silently repaired;
- the same valid payload produces the same semantic artifact;
- write receipts bind input, output, schema, source identity, and validation;
- existing manually maintained artifacts remain compatible;
- tests include malformed payloads, multiline text, special characters, duplicate keys, unknown fields, interrupted writes, stale updates, and unauthorized status transitions;
- small-model evaluation demonstrates fewer mechanical retries without weakening semantic checks.

## Planning Questions

A detailed implementation plan should determine:

1. Which existing DeltaFuse schemas can directly drive writer operations.
2. Whether the public interface should be CLI commands, tool calls, or both.
3. How typed partial updates should preserve comments and formatting, if preservation is required.
4. Which metadata belongs to the Artifact Writer and which must be supplied or verified by Core.
5. How optimistic concurrency should reject updates against stale artifact hashes.
6. Which artifact types should be included in the first migration.
7. How existing skills, templates, validators, installers, and smoke tests must change together.
8. How to evaluate improvement specifically on smaller local models.
9. How to ensure that reduced YAML failure rates do not conceal semantic regressions.
10. Whether JSON should be the internal interchange format while YAML remains the human-facing representation.