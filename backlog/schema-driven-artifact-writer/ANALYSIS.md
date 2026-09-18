# Analysis of the proposed approach

## Verdict

The approach addresses a real separation-of-concerns problem. It should reduce
serialization/rewriting burden and make failures easier to attribute. Adopt it
with three changes: schema-driven does not mean schema-only; generic patches
must never grant Core authority; and compatibility must distinguish preserving
semantic values from preserving original bytes/comments.

Keep JSON as the machine interchange and existing YAML/Markdown as storage.
Provide a callable Python API plus a CLI over exactly the same validation and
authorization path. Tool definitions can be exported per kind/operation; a host
adapter is a consumer, not another serializer or a new runtime role.

The benefit for smaller models is plausible, not measured yet. JSON syntax can
also fail. Tool-call constraints and concise targeted errors complement the
writer; they do not replace semantic/evidence checks.

## Observed baseline and evidence

Read canonical docs, schemas, templates and current implementation at
17786cb040d1ed3cd5636dd4a6b97453c1b77627 / VERSION 3.1.0.
No external product claims are used. Symbol names below are source navigation
anchors for the implementation model.

| Finding | Current source | Implication |
|---|---|---|
| SchemaRegistry already loads Draft 2020-12 schemas and offers useful hints | src/deltafuse/core/schemas.py: SchemaRegistry, format_schema_error | Extend structured diagnostics; do not fork a competing schema engine |
| The registry resolves packaged assets and has fallback behavior | core/schemas.py.__init__, core/assets.py.resolve_assets | Writer must pin exact schema bytes and lock, and reject mismatches; no convenient CWD fallback on writer path |
| Duplicate frontmatter keys silently take the last value | core/frontmatter.py.parse_frontmatter, yaml.safe_load | Strict parser is needed before update can claim lossless semantic preservation |
| Frontmatter parsing strips whole-document whitespace; replacement reserializes metadata/body | core/frontmatter.py.parse_frontmatter/replace_frontmatter | Existing helper is not byte-preserving; do not reuse it unchanged for opaque prose |
| Existing scaffold includes created, omits required contract fields | core/scaffold.py._change_yaml versus process/schemas/change.schema.yaml | Complete validated creation needs a separate scaffold repair; serializer must not invent absent semantics |
| Date format is not enforced by the current registry configuration in the probe | SchemaRegistry._load_all_schemas | Decide/enable writer format assertions explicitly and test compatibility; do not assume format annotations validate |
| state, advance and decide already own lifecycle/gate mutations | core/transitions.py, core/decide.py, cli.py | Public artifact.update(status=verified) must reject and direct caller to existing authority |
| Evidence is stamped by Core and baseline identity is checked separately | core/evidence.py, core/fsm.py | Structural receipt cannot mint authenticity, success or current-snapshot proof |
| Verification run is required by docs/gate, but CLI runner supports only red/green/regression with task | docs/workflow.md; skills/verify; cli.py evidence parser; evidence.run_evidence | Add Core verification runner support, not Worker-authored passed YAML |
| coverage is already mechanically derived | core/analyze.py.build_coverage_document/write_coverage | Reuse writer internally; do not expose a second Worker-owned coverage truth |
| Artifact schemas are not uniformly closed | routing/coverage allow top-level extra properties; change has open nested objects | Typed input adapters need closed operation schemas; existing schema-valid extensions must not silently disappear |
| Nested artifacts inherit schema_version from Change | task/slice/spec-delta/decision schemas | Do not inject schema_version into every frontmatter; many would reject it |
| Framework release 3.1.0 still uses artifact schema_version 3 | VERSION and process/schemas | Keep release, operation, serializer and artifact-schema identities separate |

The in-memory probe was run with repository CPython 3.12.14 and PyYAML 6.0.3.
Results are preserved under evidence/. It demonstrated last-key-wins, body
whitespace loss, scaffold schema errors, and non-enforcement of date format.
These are characterization results, not new failing tests committed to tests/.

The sandbox could not launch the repository Python initially. The bundled
Python lacked PyYAML. A permitted host execution of the repository interpreter
ran the read-only probe successfully with bytecode disabled. No dependencies
were installed. Framework smoke and qualification suites were not run for this
planning-only change.

## What cannot be derived from an artifact schema

A storage schema describes shapes, required keys and enums. It does not establish:
which stage may edit a field; which actor can accept a Decision; whether a path
belongs to this Change; whether a reference was measured; whether two state
files agree; whether a task can transition; or how to recover a crash.
Use a small operation descriptor over the authoritative storage schema, with
Core policy callbacks and a serializer policy. Do not create a universal
schema interpreting every artifact or accept caller-supplied authority flags.

Fields have four categories:
Worker-authored semantic content; Core-resolved identity; Core-owned state/
evidence; formatting-only metadata. Required does not imply auto-generated.
Defaults are allowed only where a specific creation contract already defines
them. Existing defaulting bugs are not a license to guess user intent.

## Initial scope adjustment

The proposal's requirement_delta object is illustrative, not an existing
artifact type. Current task.requirement_delta is an enum; spec-delta.md is a
different existing frontmatter artifact. There is no universal requirement
index schema to reuse. Do not add a product requirement schema just to fit the
example.

Support the actual registry in CONTRACT.md. Start with compact frontmatter and
routing; treat substantial Markdown bodies as opaque authored content.
request.md, analysis.md and verification.md do not all share one schema.
Keep untyped narrative documents manual until a separate explicit contract is
justified. Core-only evidence/status/scaffold integration is part of the
feature, but never exposed as arbitrary Worker field writes.

## Format and compatibility decision

MVP guarantees unchanged schema-valid unpatched values and exact opaque body
bytes on metadata-only update. It does not promise preservation of metadata
comments, quoting or key order. Canonical create output has stable ordering,
UTF-8, LF metadata and safe scalar styles.

For an existing noncanonical metadata segment, preview the formatting change
and require explicit per-operation canonicalization opt-in before updating.
Detect this by comparing the old metadata bytes with canonical serialization
of the old mapping; do not attempt unreliable regex comment detection.
Read-only validation remains available without conversion. No bulk rewrite or
automatic migration. Body newline/BOM/encoding policy is explicit and tested.

This avoids a new round-trip YAML dependency in the first increment.
If transparent metadata comment preservation becomes mandatory, create a
separate codec decision and compatibility corpus; do not claim PyYAML
safe_dump preserves comments. A formatting refusal is classified separately
from a semantic/schema error in the experiment.

## Persistence and concurrency

Prevalidate the entire candidate and parse/revalidate serialized temporary
bytes before publication. Post-write read-back adds an integrity check;
it must not be the first time an invalid candidate is discovered.

A file replace is not a transaction covering target + receipt + transition
journal + sibling indexes. Introduce a recoverable transaction protocol with
known before/after hashes and explicit outcome states. Existing transition
journal semantics must be preserved or migrated with tested recovery,
not wrapped in another uncoordinated receipt log.

Optimistic hash checks without locking have a race. Cooperating Core writers
must share a product-level mutation lock and recheck target plus authority/
snapshot inputs under that lock. Direct editor/raw-shell writes do not honor
portable advisory locks. Document that limitation, detect drift, and rely on
host OS write restrictions for hostile concurrency guarantees; do not promise
an impossible portable filesystem compare-and-swap against arbitrary writers.

Create must publish with no-replace semantics. exists()+os.replace() can
overwrite a concurrently created file and is not an acceptable create.
Windows sharing/ACL/reparse cases and POSIX permissions/link cases need real
platform tests. No fallback to truncating the existing artifact on failure.

## Safety and semantic checks

Authorization precedes access to protected targets; path resolution, active
Change/stage/operation, lock pin and per-field ownership are checked before
prepare and again at commit. A null Worker envelope is not universal access.
Existing leash exemptions are not permission to modify .deltafuse or immutable
intake through a generic writer.

Validation reports scopes independently: syntax, schema, identity, references,
Core invariants. Calling artifact.validate never runs tests, accepts Gates or
advances status. Partial artifacts do not need a whole future lifecycle to
be complete; missing required current references fail, while declared future
file operations are judged by their phase-specific contract. Deferred whole-
Change checks are labelled not evaluated, never green.

Receipts bind values/hashes/policy, not truth of arbitrary prose. Public hashes
and current evidence stamps are integrity checks, not cryptographic proof of
a trusted execution origin. Existing independent evidence checks remain required.

## Answers to the ten planning questions

1. Reuse task/slice/spec-delta/routing/change/evidence storage schemas with
   operation adapters; see the catalog. Coverage/state/evidence use Core callers.
2. Shared Python service + CLI first; generated small tool argument schemas
   second, with thin host wrappers. No editor/plugin implementation in Core.
3. Preserve opaque body bytes and unpatched values; explicit metadata
   canonicalization for legacy formatting/comments. Round-trip comments deferred.
4. Schema identity/formatting belong to Writer; source/lock/state/evidence facts
   come from Core; timestamp supplied once by a transaction context if required.
5. Required before hash + common mutation lock + authority fingerprint +
   recheck + no-op/retry protocol; disclose noncooperating-writer limitation.
6. Compact typed frontmatter/routing and controlled Change updates, followed by
   internal evidence/status/scaffold/coverage consumers. No universal prose YAML.
7. Docs/skills/templates/operation schemas, Core validators, asset bundle,
   installed wheel and both smoke/layout paths change together.
8. Paired raw-authoring/writer trials with same model/profile/context/cases,
   clean sessions, randomized order and telemetry.
9. Same independent semantic/gate/evidence oracle in both arms; count unsupported
   operations, JSON errors, canonicalization refusals and attrition explicitly.
10. Yes: strict bounded JSON interchange, existing human-facing artifact formats.
