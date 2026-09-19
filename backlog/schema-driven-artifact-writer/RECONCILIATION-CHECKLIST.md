# Literal acceptance reconciliation checklist

Apply this to each task before completion and again in AW-42/AW-20.
This is an evidence audit, not permission to check boxes without executing work.

1. Load original CONTRACT.md/VALIDATION.md, selected card, queue acceptance IDs,
   latest review and result. Compare authoritative requirement text with each
   result row VERBATIM. Any narrowed wording fails reconciliation.
2. Expand every compound requirement into subrows while retaining the original
   parent. A parent is PASS only if every mandatory child has actual PASS evidence.
3. For each claimed PASS, open the actual raw evidence and verify its source,
   input, public command, exit, expected artifact effects and exact required host
   or model identity. If evidence is missing, record NOT RUN; do not infer PASS.
4. Test missing ID separately from wrong ID. Inspect before/after artifacts,
   journals and receipts to establish that denial preceded mutation.
5. Inspect installed-schema damage tests: prove the packaged schema was present,
   then actually removed or changed without updating its manifest. Confirm the
   invoked CLI imported the isolated installed package. Request-field omission
   and stale artifact hashes are different invariants and do not count here.
6. Inspect paired-model evidence: real provider/model identity, preregistration,
   fresh sessions in both arms, raw requests/responses/tool attempts, independent
   oracle and computed uncertainty. Honest no-endpoint reporting passes only its
   reporting subcheck; live-session subchecks remain NOT RUN.
7. Inspect platform evidence separately for Windows and actual POSIX filesystem
   behavior. Mandatory privileged/symlink/reparse checks cannot pass through a
   skip or limitation disclosure. Both smoke/layout scripts require evidence.
8. Recompute source/wheel/evidence hashes and compare actual import paths and
   tested versions. Later relevant edits require rerunning affected checks.
9. Compare test inventory and invariants before/after. Each removed, narrowed,
   renamed or replaced test must retain an executable same-or-stronger invariant.
   Names, counts and a green suite alone do not establish preserved coverage.
10. Count mandatory FAIL and NOT RUN rows. If either count is nonzero, leave the
    task open. Keep result/card/queue/evaluation status consistent and name the
    exact blocker. An unavailable external resource is not implicit scope waiver.

For AW-42/AW-20 also check that no result calls an open_for_AW-20 or unavailable
model experiment completed, and no Windows-only matrix is labeled full platform
qualification. State remaining gaps explicitly. Do not publish accepted until
all original required actions have actually passed or the user has explicitly
revised scope and that revision is recorded with its changed acceptance criteria.
