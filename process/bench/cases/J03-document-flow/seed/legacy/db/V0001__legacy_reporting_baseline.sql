-- Old reporting baseline of the retired audit warehouse (superseded 2025-11).
-- Inert artifact: this file is NOT registered with any live Flyway history.
-- The live schemas are owned by the service migrations under *-service/src/main/resources/db/migration.

CREATE TABLE legacy_report_page (
    page_id      BIGSERIAL PRIMARY KEY,
    document_ref VARCHAR(128) NOT NULL,
    page_index   INTEGER NOT NULL,
    line_count   INTEGER NOT NULL,
    exported_at  TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT legacy_report_page_unique UNIQUE (document_ref, page_index)
);

CREATE TABLE legacy_report_export (
    export_id   VARCHAR(64) PRIMARY KEY,
    produced_by VARCHAR(128) NOT NULL,
    line_count  INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMP NOT NULL DEFAULT now()
);
