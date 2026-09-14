# Change request: reporting consolidation (2025-11, completed)

Status: archived (superseded by the live audit projection)
Initial: the retired FTP/SOAP ingest warehouse was the only source of audit
reporting. Pages were exported nightly into `legacy_report_export`.

## Requested outcome (historical)

Consolidate the nightly exports into a queryable warehouse with a stable
line checksum per page so exports could be verified after transfer.

## Historical resolution

A temporary warehouse (`legacy_report_page`, `legacy_report_export`) was
provisioned by `seed/legacy/db/V0001__legacy_reporting_baseline.sql`. The
2026 audit-service replaced it with the live append-only projection; the
warehouse and the FTP drop were decommissioned and their artifacts archived
under `seed/legacy/`. No live service references any of these objects.

This archive exists so the history of the reporting path stays inspectable.
It imposes no requirement on the current product.
