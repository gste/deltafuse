CREATE TABLE command_receipt (
    operation_id VARCHAR(128) PRIMARY KEY,
    command_type VARCHAR(32) NOT NULL CHECK (command_type IN ('CREATE_DOCUMENT', 'CREATE_VERSION', 'SUBMIT_VERSION')),
    request_payload JSONB NOT NULL,
    result_document_id VARCHAR(128) NOT NULL,
    result_version_id VARCHAR(128),
    result_state VARCHAR(16) NOT NULL CHECK (result_state IN ('DRAFT', 'SUBMITTED')),
    result_event_id VARCHAR(128) NOT NULL UNIQUE,
    result_domain_sequence BIGINT NOT NULL CHECK (result_domain_sequence >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX one_draft_version_per_document
    ON document_version (document_id)
    WHERE state = 'DRAFT';
