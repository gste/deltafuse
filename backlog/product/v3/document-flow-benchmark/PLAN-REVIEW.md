# Planning validation — J03-plan-1

Status: planning validation passed; **not benchmark implementation evidence**.

Checks performed on the generated plan payload:

- 58 unique task IDs; all statuses planned.
- 85 dependency edges reference existing preceding cards. One ordered pass
  inserts each card into a visited set and requires every dependency already
  visited, proving the published order is topological and the graph acyclic.
- Each card has an invariant, input/output sets, ordered work, Red counterexample,
  Green acceptance, verification procedure, and handoff/result path.
- Seven stage correctness groups each sum to 600; common discipline sums to
  250 per stage; efficiency allocation is 150. Seven stages total 7000.
- System groups sum to 1800+600+400+200=3000.
- 84 scored check IDs plus six absolute non-point check IDs are defined.
- All 28 unique mutants map to existing implementing cards and defined checks.
  27 are critical; 90% of 28 requires at least 26 total kills but all 27
  critical candidates still must be detected.
- All fifteen source acceptance criteria are mapped in COVERAGE.md.
- 440 relative Markdown links within the generated bundle resolve to bundle
  files or the existing INSTRUCTION.md/DESIGN.md/READINESS.md.
- Package counts: 00=4, 01=8, 02=10, 03=8, 04=9, 05=8, 06=5, 07=6.

## Review corrections incorporated

- Package 02 depends on both campaign arithmetic and evidence-store completion,
  preventing a skipped package-01 branch.
- Package 04 starts after the package-03 oracle/system exit card.
- File focus uses unique files as requested by the intention document, with
  separate byte-range/repository-dump diagnostics; earlier design's byte-ratio
  proposal is superseded.
- Stage reentry uses immutable visits and terminal seven-stage rollups;
  no earlier snapshot is reconstructed from the final tree.
- A full positive reference needs actual Java behavior AND a valid process
  fixture with authentic Core/Gate evidence.
- M21 scripted attack calibration is labelled defense evidence, not proof of
  model susceptibility. Actual model behavior belongs to the later pilot.
- Cross-platform build evidence distinguishes Windows, Git Bash and Linux/WSL.
- Docker availability updated from an actual host read; Java/stack/model remain
  future preflight, not claimed unavailable because the old daemon check failed.

## What was not executed

No framework or benchmark implementation, Java build, container stack,
mutation calibration, model inference, external Worker pilot or campaign.
The checks above validate planning structure and arithmetic, not future
implementation correctness. Every executable acceptance remains planned.

Revalidate queue dependencies, registry totals, mutation check IDs and links
whenever cards/contracts change. Readiness is established later by J03-000,
and benchmark acceptance only by evidence reconciliation in J03-706.
