ALTER TABLE audit_event ADD COLUMN aggregate_type VARCHAR(16) NOT NULL DEFAULT 'DOCUMENT'
    CHECK (aggregate_type IN ('DOCUMENT', 'ROUTE'));
ALTER TABLE audit_event ADD COLUMN aggregate_id VARCHAR(128) NOT NULL DEFAULT 'legacy';
ALTER TABLE inbox_event ADD COLUMN event_payload JSONB;
UPDATE inbox_event SET event_payload = '{}'::jsonb WHERE event_payload IS NULL;
ALTER TABLE inbox_event ALTER COLUMN event_payload SET NOT NULL;
CREATE INDEX audit_event_aggregate_order ON audit_event(aggregate_type, aggregate_id, sequence, event_id);
