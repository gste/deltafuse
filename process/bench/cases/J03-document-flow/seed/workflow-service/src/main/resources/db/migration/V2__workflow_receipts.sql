CREATE TABLE route_receipt (
    input_event_id VARCHAR(128) PRIMARY KEY REFERENCES inbox_event (event_id),
    request_payload JSONB NOT NULL,
    result_route_id VARCHAR(128) NOT NULL UNIQUE REFERENCES route (route_id),
    result_document_id VARCHAR(128) NOT NULL,
    result_version_id VARCHAR(128) NOT NULL,
    result_approver_actor_id VARCHAR(128) NOT NULL,
    result_event_id VARCHAR(128) NOT NULL UNIQUE,
    result_domain_sequence BIGINT NOT NULL CHECK (result_domain_sequence = 1)
);

CREATE TABLE decision_receipt (
    route_id VARCHAR(128) NOT NULL,
    decision_id VARCHAR(128) NOT NULL,
    operation_id VARCHAR(128) NOT NULL,
    request_payload JSONB NOT NULL,
    result_event_id VARCHAR(128) NOT NULL UNIQUE,
    result_state VARCHAR(16) NOT NULL CHECK (result_state IN ('APPROVED', 'REJECTED')),
    result_domain_sequence BIGINT NOT NULL CHECK (result_domain_sequence = 2),
    PRIMARY KEY (route_id, decision_id),
    FOREIGN KEY (route_id, decision_id) REFERENCES decision (route_id, decision_id)
);

CREATE UNIQUE INDEX one_pending_route_per_document
    ON route (document_id)
    WHERE state = 'PENDING';
