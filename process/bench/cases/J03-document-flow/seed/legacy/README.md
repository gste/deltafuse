# Retired legacy ingest adapter (archived 2025-11)

This directory preserves the retired FTP/SOAP ingest adapter that preceded
the live HTTP APIs. It is **not a Maven module**: nothing here compiles into
the services, nothing here runs, and no service class imports from it. It is
kept verbatim for archive tooling and as realistic history of the product.

- `adapter/LegacyIngestAdapter.java` — the retired ingest entry point.
- `db/V0001__legacy_reporting_baseline.sql` — the old reporting migration of
  the retired warehouse (superseded by the live Flyway histories; kept as an
  inert artifact, never registered).
- `config/legacy-ingest.properties` — last known configuration of the
  retired drop (no credentials; the endpoint was decommissioned).

Do not revive this code. The live baseline is the three-service stack
described in the root README.
