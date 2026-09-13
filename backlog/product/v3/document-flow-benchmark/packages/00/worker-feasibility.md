# J03 external Worker instrumentation feasibility

Status: feasible with mandatory adapter controls
Card: J03-001
Tested DeltaFuse source: `c0f70ef067fc6f711d315de0956012a41e9b3a70`
Evidence ID: `J03-001-local-probe-20260913`

## Installed identities

| Component | Observed identity | Source and SHA256 |
|---|---|---|
| little-coder | npm package `1.19.0` | `package.json` — `bbb6d4099e37bf991eb60f52033c2ffdb3aff50551e4119ec1a57a064a42b3f0` |
| Pi coding agent | `@earendil-works/pi-coding-agent` `0.83.0` | nested `package.json` — `e02deae1cec07035807436c1864c88342e2f7d49050d03b858a3719f0c7aedbf` |
| Node | `v24.15.0` | `node --version`, exit 0 |
| npm | `11.12.1` | `npm --version`, exit 0 |
| launcher | installed little-coder entrypoint | `bin/little-coder.mjs` — `896dfca384ce2d2a3280c4b50f5e4107866e59d89dea95b189bdd9086b7372d2` |
| RPC contract | Pi JSON-lines types | `rpc-types.d.ts` — `122dec2245c472e15b71b6114c760eaf67937266482548e3bbafe2f13936aacc` |
| RPC transport | Pi session-event forwarder | `rpc-mode.js` — `19590dfe20a31384ab68e6aa75264b92ac82a210766e7f1169f898d2bd7cfc83` |

`little-coder --version` prints `0.83.0`, the Pi version, not little-coder's
`1.19.0`. Release attestation must therefore hash/read the wrapper package and
launcher; the CLI version string alone is not a wrapper identity.

## Observation and control matrix

| Requirement | Versioned source / transport | Scripted probe | Classification and remaining work |
|---|---|---|---|
| Active model | RPC `get_state` returns provider, model id, API, base URL, context window and maximum output | Returned persisted `llamacpp/qwen3.8-27b`, context 32768 | Observable. J03-506 must bind this to configured/provider attestation and detect changes. |
| Thinking level | RPC `get_state`, `set_thinking_level`, and `thinking_level_changed`; thinking-budget source SHA `eff24e2dd1cf9ae30657081a1e6d4dfedf68b4d0c4b13526379cc352bbe86b50` | Returned `medium`; supported levels off/minimal/low/medium/high | Observable state. Actual retained reasoning bytes/tokens require J03-502; do not infer them from level. |
| Model switching | RPC `model_select` session events plus phase-model extension SHA `747dec54aa04b51d40889acaf80b4bcb63a339f2b85015c902759f67cc5ca4d3` | Initial active model observed without a model call | Mechanism observable. J03-506 must fail on unregistered switches, including phase handover. |
| Model requests | Pi extension hook `before_provider_request` can inspect payload; response status/headers hook also exists | Not invoked because this card forbids model inference | Feasible only through a judge-owned extension loaded explicitly. J03-501/J03-502 must hash request/response boundaries. |
| Usage/tokens | Assistant messages carry provider `Usage`; compaction result carries `usage` | No model call | Counts may exist, but usage provenance is not labelled measured versus estimated. Context/compaction code explicitly uses estimates. J03-502 must record provider-native fields and null unsupported provenance; estimates cannot score. |
| Tool calls/results | RPC forwards `tool_execution_start/update/end` with call id, name, args, result and error | Extension UI and command-source events observed | Observable for model tool execution. J03-503 must preserve native envelopes and denials. |
| Compaction | RPC forwards `compaction_start/end`; result has reason, tokensBefore, optional estimatedTokensAfter and summarizer usage; context-watchdog SHA `fdbae2699af447f60f9d75785139bfb31d4af9a70e1539b487e70dad7d82c4e2` | State reported `isCompacting=false`, auto-compaction enabled | Events observable, but after-size is explicitly optional/estimated. J03-502 must distinguish measured/null from estimates and test real compaction later. |
| Extension inventory | Launcher uses `--no-extensions` plus explicit bundled/user paths and exports a manifest; user discovery SHA `5c52ed467f442e2d7ba345540a7f84f227863aedcf427d85ea6ff5464dc243ea` | Startup exposed extension-origin UI/commands and absolute source identities | Hashable. Qualification must set isolated config/home, reject user/extra/Pi discovery, and attest exact files in J03-506. |
| Disable dispatch/browser/fetch | Pi CLI `--tools`/`--exclude-tools`; little-coder tool-gating SHA `0498c7f37a6e27655609acdc9cc9557c3c32820b89ff0a4a74126ada28bd796d`; extension sources are hashable | Launched with `--tools read` | Model tool surface can be allowlisted. J03-503 must assert schemas and attempted calls, not merely environment declarations. |
| Plan/action substitution | Phase-model extension is versioned and RPC emits model selection | Commands `/plan-model`, `/action-model`, `/model-handover` were listed | Must be disabled or preregistered; J03-506 rejects identity substitution. |
| Shell invocation | Tool events observe bash/ShellSession calls; permission-gate SHA `13bee9538bc8a714eebee278252bfc23b4279c62ca40fe47d598eb17b413e6dc` | See Red probe below | Tool event observes command/output, not filesystem reads made by child processes. J03-504 requires OS/container boundary telemetry; event logs cannot substitute. |

## Red counterexamples

1. Identity: `little-coder --version` exited 0 with `0.83.0`; assertion that it
   uniquely identifies little-coder `1.19.0` fails.
2. RPC authority: launch used `--tools read`, then controller command
   `{"id":"bash-red","type":"bash","command":"echo J03_RPC_BASH_BYPASS"}`
   executed and returned exit 0 with `J03_RPC_BASH_BYPASS`. Pi's direct RPC
   `bash` command is outside the model tool schema/allowlist. The J03 adapter
   must parse and allowlist controller commands and must never relay arbitrary
   Worker-authored RPC objects.
3. Token provenance: Pi types expose provider usage alongside explicitly
   estimated context/compaction counts, but no transport field proves the
   source of every count. The benchmark contract therefore records unsupported
   provenance as null until J03-502 captures and validates a real provider run.
4. Shell reads: command and output events cannot reveal files opened by a child
   process. J03-504 remains mandatory; no event-based estimate is accepted.

## Scripted probe

Environment: `LITTLE_CODER_NO_UPDATE_CHECK=1`, isolated
`PI_CODING_AGENT_DIR`, offline, ephemeral session, no context files, no skills,
`--tools read`. No prompt or model request was sent.

Commands and exits:

- `node --version` → 0, `v24.15.0`.
- `npm --version` → 0, `11.12.1`.
- `little-coder --version` → 0, `0.83.0`.
- `little-coder --help` → 0; documented RPC mode and tool include/exclude flags.
- `little-coder --mode rpc --offline --no-session --no-context-files --no-skills --tools read` plus `get_state`, `get_available_thinking_levels`, and `get_commands` → successful responses without a model call.
- Same launch plus direct RPC `bash` echo probe → RPC success, shell exit 0,
  proving the required negative authority case.

## Feasibility verdict

The real external process and JSON-lines transport are suitable foundations,
but release use is conditional on J03-501 through J03-506. Existing cards cover
all discovered remedies: transport allowlisting (J03-501/J03-503), provider and
compaction measurement (J03-502), subprocess/file/network observation
(J03-504/J03-505), and immutable identity/extension/model attestation (J03-506).
No child card is required and no live qualification is claimed.
