# Analysis: reporting consolidation (2025-11, archived)

Archived analysis of the completed 2025-11 consolidation. Retained verbatim.

## Claims (historical)

- C-1: nightly exports must be verifiable page-by-page (checksum per page).
- C-2: the warehouse must not become a second write path for live audits.
- C-3: decommissioning the FTP drop must not lose archived boxes metadata.

## Historical routing

- C-1, C-2 routed to the (now retired) reporting warehouse capability.
- C-3 routed to the physical archive registry (external, unchanged).

## Historical spec delta (superseded)

Added `legacy_report_page` / `legacy_report_export` and the retired export
manifest DTOs. All superseded by the live audit projection in 2026; the DTOs
survive as `audit-service/src/main/java/dev/deltafuse/bench/audit/legacy/`
noise used by archive tooling only.
