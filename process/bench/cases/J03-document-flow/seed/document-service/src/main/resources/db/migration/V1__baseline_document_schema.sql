CREATE TABLE document (
    document_id VARCHAR(128) PRIMARY KEY,
    title VARCHAR(512) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE document_version (
    document_id VARCHAR(128) NOT NULL REFERENCES document (document_id),
    version_id VARCHAR(128) NOT NULL,
    content TEXT NOT NULL CHECK (length(content) BETWEEN 1 AND 65536),
    state VARCHAR(16) NOT NULL CHECK (state IN ('DRAFT', 'SUBMITTED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, version_id),
    UNIQUE (version_id)
);

CREATE TABLE outbox_event (
    event_id VARCHAR(128) PRIMARY KEY,
    aggregate_type VARCHAR(16) NOT NULL CHECK (aggregate_type IN ('DOCUMENT', 'ROUTE')),
    aggregate_id VARCHAR(128) NOT NULL,
    domain_sequence BIGINT NOT NULL CHECK (domain_sequence >= 1),
    schema_name VARCHAR(128) NOT NULL,
    schema_version INTEGER NOT NULL CHECK (schema_version >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (aggregate_type, aggregate_id, domain_sequence)
);

CREATE TABLE inbox_event (
    event_id VARCHAR(128) PRIMARY KEY
);
