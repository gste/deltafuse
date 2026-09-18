# Validation and smaller-model evaluation plan

No test or evaluation listed here has been executed as implementation evidence.
The saved probe only characterizes selected current behavior.

## Source acceptance mapping

| Requirement from INTENTION.md | Cards | Decisive evidence |
|---|---|---|
| Supported creation without raw YAML | AW-10/11 | Actual CLI/tool JSON creates valid kind-specific YAML/frontmatter |
| Malformed input fails before file changes | AW-02/05/06/10 | Before/after byte hashes and journal assertions for every input failure |
| Deterministic serialization | AW-04 | Same full context + reordered object keys produce identical bytes |
| Parse/schema check after writes | AW-07/09/10 | Staged prevalidation plus post-publication read-back; injected corruption non-success |
| Update preserves unrelated fields | AW-05/16 | Nested/extension values and opaque body exact-byte comparisons |
| Unauthorized state/Human Gate changes rejected | AW-06/13/17 | Direct, nested and parent-replacement attacks; actual Core gate tests |
| Semantic omissions not repaired | AW-01/03/10 | Missing title/refs/claims stays an error; no invented defaults |
| Same payload, same semantic artifact | AW-04/09 | Serializer/context identity controlled; retries reuse prepared metadata |
| Receipts bind input/output/schema/source/validation | AW-09/12 | Recomputed hashes; source/pin mismatch; crash/retry evidence |
| Manual artifacts compatible | AW-16 | Legacy corpus; read-only access; explicit canonicalization; no bulk migration |
| Malformed/multiline/special/duplicate/unknown/crash/stale/status cases | AW-02–09/17 | Full negative and platform matrix below |
| Smaller models need fewer mechanical retries without semantic weakening | AW-18/19/20 | Preregistered paired external-model results and independent semantic checks |

## Deterministic test matrix

**Input and codec**
Duplicate JSON/YAML keys at every depth; empty/nonmapping input; unsafe tags;
merge keys; recursive aliases; depth/size limits; invalid Unicode/BOM;
Markdown delimiters within body/code blocks; LF/CRLF; no/trailing newline;
quoted true/yes/null/date; numeric-looking IDs; colon/hash/quotes/backslashes;
multiline literal/folded strings; surrogate/non-BMP/Cyrillic content;
extension fields; deterministic key order without reordering semantic arrays.

**Patch and preservation**
Omission/null/remove distinctions; required-field removal; overlapping pointers;
array reindex/append attempts; escaped pointer tokens; body unchanged on
metadata-only update; explicit body replacement; parent-object replacement
of protected status; identity changes; inherited schema version; no-op;
valid extensions unknown to patch preserved; malformed legacy input refused;
comment/format change preview must match exact expected hash.

**Authority and reference**
Wrong active Change/pass/task; halt/null envelope; advisory/off leash must not
turn writer protected-field policy off; stale envelope; wrong schema/lock;
forged internal caller JSON; .deltafuse/lock/intake targets; existing refs with
wrong identity; paths that are declarations versus resolved evidence;
Windows case/ADS/device/UNC/reparse and POSIX symlink escape; check/read/write
path races within the documented cooperating-writer boundary.

**Persistence and receipts**
Two creates at same path; two stale updates; target absent/unexpected existing;
change to body/comment without metadata change; sharing violations/permission
denial; disk full; temporary-file parse mismatch; crash before/after each
journal/replace/fsync/read-back/receipt point; receipts missing after publication;
same request ID identical/different payload; third-party edit during recovery;
old transition journal replay; no repeated evidence execution on receipt retry.
Observe actual Windows and POSIX behavior, not only monkeypatched replace.

**Semantics/Core**
Passed evidence forged by a Worker; stale baseline; invalid runner; timeout;
verification phase/task:null exact path; correct no-op route; real Human Gate
pause/reject/accept semantics; invalid transition remains rejected even though
enum is valid; whole-Change incomplete checks not mislabeled fully validated;
coverage points to real artifacts; scaffold shape matches claimed status;
invalid field errors remain small and actionable without heuristic renaming.

## Required existing checks for runtime implementation

Resolve actual interpreter and environment at the tested commit; no WindowsApps
shim assumptions. Run card-specific tests first, then affected regression suites.
At phase F:
- Full pytest with immutable results outside tracked source.
- tests/smoke-test.ps1 and tests/smoke-test.sh.
- tests/validate-layout.ps1 -ProductDir <fresh-installed-product> and
  tests/validate-layout.sh <fresh-installed-product>.
- scripts/sync_assets.py --check after intentional asset generation.
- Built-wheel install without source checkout; describe/create/update/validate
  work with pinned operation schemas and generated skill/lock identity.
- Legacy path/command search; classify history/negative-test hits rather than
  declaring every string hit a defect.
- Windows + actual POSIX concurrency/crash tests. Git Bash smoke alone is not
  proof of POSIX filesystem crash semantics. Report unavailable checks.

Changing shared parser behavior requires all existing consumers' regression
coverage. Do not blindly replace permissive readers repo-wide in one step.
Generated assets are updated from canonical sources, not hand-edited.

## Paired smaller-model evaluation

Question: does the writer reduce *mechanical* failed attempts while preserving
semantic correctness and existing gate/evidence enforcement?
Do not infer the answer from Python serializer unit tests.

Primary arms:
A. Current manual authoring using existing skills/validators.
B. Typed Artifact Writer using same model and independent semantic oracle.
Optional C. Typed writer plus constrained decoding/tool schema support.
Separate B versus C so constrained decoding gains are not all attributed
to persistence/serialization. Provide equivalent product intent and relevant
context, with only the necessary interface instruction difference.

Freeze before running:
- model/provider/weights or available identity, agent version, thinking,
  tokenizer/context and total task budgets;
- both framework variants, serializer/schema/skill hashes and available tools;
- matched corpus, independent expected semantics and adversarial bypass cases;
- randomized/counterbalanced arm order, fresh sessions and attempt limits;
- sample/seed count, stopping/missing-data rules and success criterion.

Proposed corpus strata: task and slice creation; routing; spec-delta with
multiline prose; nested partial updates; explicit null/removal; inherited
version metadata; legacy comments; stale update; missing semantic references;
illicit status/accepted Decision; genuine Core evidence with source drift.
Include unfamiliar held-out artifact contents and values, not just template
copies. Balance create/update and short/prose-heavy inputs.

Start with a small pilot for harness correctness; keep it separate from the
frozen measured experiment. Size the final paired sample for the declared
effect/uncertainty target before collecting outcomes. If only a small sample
is affordable, label the result exploratory; do not claim general model gains.

Primary metrics:
- first-pass structurally valid artifact rate;
- mechanical failed attempts and retries per assigned case (both raw YAML and
  typed JSON/unknown-field/formatting failures count);
- independently semantically correct completed artifacts per assigned case;
- forbidden state/Gate/evidence requests successfully blocked.

Secondary: total tool calls, input/output tokens, time diagnostics, bytes/fields
rewritten, refusals requiring formatting opt-in, schema vs policy vs semantic
errors, incomplete/unsupported runs. Do not silently exclude timeouts, invalid
runs or failures from denominators; disclose infrastructure failures separately.

The oracle operates on resulting artifact meaning, provenance and unchanged
Core gates, identically for both arms. Writer receipts are not ground truth
for semantic success. Include intentional weakened-writer controls (drop
required semantic value, default verified, accept duplicate, fake evidence
stamp): the evaluation must detect them.

Report paired per-case differences and uncertainty, by stratum and overall.
Freeze the confidence/non-regression decision rule during AW-18. A benefit
claim requires a demonstrable mechanical reduction and no violation of hard
semantic/authority gates; no observed semantic degradation is necessary but
does not prove universal noninferiority. If uncertainty is too large, report
inconclusive and keep the performance criterion open. Never tune thresholds
after results or reward the writer for silently completing missing semantics.

Raw prompts, structured payloads, retry errors, artifacts, receipts and real
model identities remain distinguishable. Do not store API keys. Missing
endpoint access is a prerequisite, not permission to simulate a successful
small-model result. The current planning task performs no such runs.
