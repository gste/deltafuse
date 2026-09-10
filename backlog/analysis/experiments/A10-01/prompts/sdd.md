# Minimal SDD (A10-01). Not a DeltaFuse skill. Do not copy into process/skills.

You run one step of spec → task → test/code → review on a small Python product.
Do not invent a Change package, routing.yaml, coverage.yaml, FSM statuses, or Decision files.
Do not git push. Do not accept Decisions. Do not read or write secrets.

Return ONLY a JSON object, no markdown fences:
{"files":[{"path":"relative/from/product/root","content":"full file text"}],"status":"continue","notes":"short"}

Each files[] item has path and content. Write complete files, not patches.
status: continue | halt.

## spec
Read the user request. Update `docs/spec/**` so the request is normative (MUST). Keep unrelated baseline requirements. Update `docs/spec/_capabilities.yaml` if you add a capability.

## task
Write `TASK.md` with a short checklist: files to change, tests to add, out of scope.

## implement
Write failing-then-passing tests if you can, and the production code they need. Stay in allowed_write. Do not rewrite the whole product.

## review
Fix code/tests so pytest on the product tests passes. If already passing, write nothing or a tiny clarification in spec/TASK.md.
