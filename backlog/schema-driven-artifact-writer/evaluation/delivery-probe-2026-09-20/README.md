# Prompt-delivery verification — 2026-09-20 (AW-40 transport defect confirmed)

## Question

Was the 2026-09-20 "endpoint unsuitable" verdict (see `../live-run-2026-09-20/README.md`,
now superseded) caused by the model endpoint or by prompt delivery at the
child-process boundary? Prior sessions in a sibling project had multiline-argv
problems, so delivery had to be verified before any tooling verdict.

## Method

`../delivery_probe.py` replays the exact frozen CASE-01 Arm B multiline prompt
(`arm_b_prompt`, 342 bytes, 2 newlines, SHA256
`a7a5bc372ad97af8974d172df86da3c137c756a955347b77c87ad05cc4d00970`) through
each transport with the user-supplied observability extension
(`C:\Users\ghost\workspace\gste\little-coder-extensions\observability-extension\index.ts`,
NDJSON traces under `.pi\observability\`), then byte-compares the
model-visible messages (`message.final` outgoing and the serialized
`llm.request`) against the intended prompt.

Transports (one fresh model call each):

1. `cmd-shim` — frozen invocation path (`little-coder` → npm `.CMD` shim → cmd.exe).
2. `node-direct` — `node.exe …\little-coder.mjs`, cwd = deltafuse repo.
3. `node-direct-neutral` — same, cwd = fresh empty temp dir.

## Results

| Transport | Captured user message | byte_identical | Model output |
| --- | --- | --- | --- |
| `cmd-shim` | first line only: `'Output ONLY JSON for a task create:'` (SHA256 `a5011f95c7f7bb4850f11eb4183ffecb827cae2aa96ec6596a73d05362e57939`) | **False** | fabricated unrelated task list |
| `node-direct` | full multiline prompt | True | exact requested JSON (code-fenced) |
| `node-direct-neutral` | full multiline prompt | True | exact requested JSON, no extra fields |

Direct python-subprocess argv check on the same host: the prompt reaches a
child process intact (sha256 identical), isolating the loss to the
`.CMD`/cmd.exe boundary — cmd.exe terminates the quoted argument at the first
line break, silently dropping the payload line and the instruction line.

Additional finding: with a repository cwd, little-coder core injects the
repo `AGENTS.md` as an extra user message inside `llm.request` (visible in
`arm-b-case01-multiline-node-direct-trace.ndjson`); a neutral temp cwd removes
it (`node-direct-neutral` trace contains only the intended user message).

## Consequence

The "endpoint unsuitable" verdict was premature and is RETRACTED. Recorded as
AMEND-3 in `../live-run-2026-09-20/spec.json`: measured calls use the
node-direct neutral-cwd transport with per-call delivery verification
(captured prompt must equal intended, else `infra_invalid` and retried
outside the model attempt budget).

## Files

- `delivery_probe.py` (parent directory) — probe driver.
- `arm-b-case01-multiline.json` + `-cmd-shim` pair — cmd-shim run (intended
  vs truncated capture). Note: the first run's result JSON was written before
  the transport suffix existed; it is the cmd-shim evidence.
- `arm-b-case01-multiline-node-direct.{json,-trace.ndjson}` — node-direct run.
- `arm-b-case01-multiline-node-direct-neutral.{json,-trace.ndjson}` — neutral-cwd run.

## Artifact hashes (SHA256)

- `delivery_probe.py` (parent dir) `8395f1c7b35255b2284c4e9f9d0afa192418787a654cec4109cf31b529206ba5`
- `arm-b-case01-multiline.json` `bed33eed0cfbfddc66d4d15058b39ab45f982601c942cf6ee4233c9cf6149ccd`
- `arm-b-case01-multiline-trace.ndjson` `5cfbbfa0014ca2dc4e53b05ca92c1f9949ebdbf608508bb33f420a5f89b72f0b`
- `arm-b-case01-multiline-node-direct.json` `ea5f60836dde9ce505e0aba377dfebe132c640c2e24d63ed1b944d3f192fe0ab`
- `arm-b-case01-multiline-node-direct-trace.ndjson` `5f81bace82f3f96464476a27ff64b901937ddd7f254215ce607d10c61f2d56a6`
- `arm-b-case01-multiline-node-direct-neutral.json` `c3bd2febd2c3366510e2c62787928d1ec0f64034659e51508efc8d0cb7b27592`
- `arm-b-case01-multiline-node-direct-neutral-trace.ndjson` `27527dea8934ce1f2df41e2f70434900547b86e8d1aa09dd6518b5321e362d18`
