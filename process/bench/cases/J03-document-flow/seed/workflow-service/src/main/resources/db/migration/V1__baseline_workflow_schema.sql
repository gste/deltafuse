CREATE TABLE route (
    route_id VARCHAR(128) PRIMARY KEY,
    document_id VARCHAR(128) NOT NULL,
    version_id VARCHAR(128) NOT NULL,
    approver_actor_id VARCHAR(128) NOT NULL,
    state VARCHAR(16) NOT NULL CHECK (state IN ('PENDING', 'APPROVED', 'REJECTED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, version_id)
);

CREATE TABLE decision (
    route_id VARCHAR(128) NOT NULL REFERENCES route (route_id),
    decision_id VARCHAR(128) NOT NULL,
    actor_id VARCHAR(128) NOT NULL,
    role VARCHAR(32) NOT NULL CHECK (role IN ('approver')),
    action VARCHAR(16) NOT NULL CHECK (action IN ('APPROVE', 'REJECT')),
    resulting_state VARCHAR(16) NOT NULL CHECK (resulting_state IN ('APPROVED', 'REJECTED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (route_id, decision_id)
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
