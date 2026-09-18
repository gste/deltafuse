# One-card implementation handoff

Work in the canonical DeltaFuse repository selected for this feature.
Read its AGENTS.md, then README.md, PLAN.md and CONTRACT.md in this folder.
Use queue.json to select the first planned card whose dependencies have actual
completion evidence. Initially that is AW-00.

Read only the selected card's input paths and relevant sections. Wildcards are
search boundaries: use rg to locate a small set of relevant files/functions,
not instructions to concatenate directories. Keep a single invariant and
reviewable diff in the implementation model's context. Split into dependency-
ordered child cards if needed; retain all original acceptance requirements.

Per card:
1. Verify version/HEAD/status and predecessor evidence. Preserve unrelated edits.
2. Add a meaningful failing test of the invariant; capture exact Red reason.
3. Implement inside the write set. Shared contract scope adjustments are explicit.
4. Run Green and affected regressions; real platform/agent tests stay distinct
   from mocks. Stop on evidence of a design contradiction; do not weaken checks.
5. Save results/<ID>.md with full parent/tested SHA, source/contract hashes,
   exact argv/exits, artifact refs/hashes, platform, limitations and next task.
6. Update queue/card status only when acceptance is met. Finish one card and
   provide a continuation prompt naming the next evidence-ready card.

Implicit allowed writes: narrow test fixtures/package scaffolding required by
the card, its own result/status and queue entry. No unsolicited cleanup of old
backlog, no benchmark continuation, no product-specific requirements, no
global Git configuration changes, no destructive Git/push/default-branch merge.
Do not commit unless authorized; when committing, stage only owned changes.

Source precedence: user intent -> canonical Process/authority contracts ->
reviewed operation contract -> implementation convenience. Writer cannot
interpret a schema enum as permission to change state or accept a Gate.

The results file must separate structural serialization success, Core
validation scopes, artifact semantic correctness and execution-evidence truth.
Successful writer output alone proves neither convergence nor qualification.

## Copy-paste start prompt

Implement the Schema-driven Artifact Writer plan in the canonical DeltaFuse
repository. Read backlog/schema-driven-artifact-writer/README.md, EXECUTOR.md,
PLAN.md and the relevant CONTRACT.md sections. Select one dependency-ready
card from queue.json, starting with AW-00 when none are complete. Recheck
current contracts and repository status. Preserve unrelated changes. Execute
the card with meaningful Red/Green tests, record exact evidence and update
its result/status. Do not broaden status/evidence authority, invent semantic
defaults, or replace live platform/model tests with mocks. End with the next
ready card and a precise continuation prompt.
