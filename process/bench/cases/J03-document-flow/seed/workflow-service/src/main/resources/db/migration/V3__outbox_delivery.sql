CREATE TABLE outbox_delivery (
    event_id VARCHAR(128) PRIMARY KEY REFERENCES outbox_event (event_id),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    sent_at TIMESTAMPTZ,
    last_attempt_at TIMESTAMPTZ
);
