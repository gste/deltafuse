CREATE TABLE audit_event (
    event_id VARCHAR(128) PRIMARY KEY,
    document_id VARCHAR(128) NOT NULL,
    sequence BIGINT NOT NULL CHECK (sequence >= 1),
    kind VARCHAR(128) NOT NULL,
    payload JSONB NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, sequence)
);

CREATE TABLE inbox_event (
    event_id VARCHAR(128) PRIMARY KEY
);
