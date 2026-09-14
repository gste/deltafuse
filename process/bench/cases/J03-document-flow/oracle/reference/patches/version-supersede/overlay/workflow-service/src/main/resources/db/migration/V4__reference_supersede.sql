-- Reference supersede schema (private judge overlay, J03-303).
-- Applied only to fresh seed copies of the reference; never part of the
-- public seed's Flyway history.

-- The target route vocabulary adds SUPERSEDED (input.md REQ-SUP-004).
ALTER TABLE route DROP CONSTRAINT route_state_check;
ALTER TABLE route ADD CONSTRAINT route_state_check
    CHECK (state IN ('PENDING', 'APPROVED', 'REJECTED', 'SUPERSEDED'));

-- Late decisions are recorded as receipts with the IGNORED_LATE_DECISION
-- state and a route-aggregate sequence beyond the decision event.
ALTER TABLE decision_receipt ALTER COLUMN result_state TYPE VARCHAR(32);
ALTER TABLE decision_receipt DROP CONSTRAINT decision_receipt_result_state_check;
ALTER TABLE decision_receipt ADD CONSTRAINT decision_receipt_result_state_check
    CHECK (result_state IN ('APPROVED', 'REJECTED', 'IGNORED_LATE_DECISION'));
ALTER TABLE decision_receipt DROP CONSTRAINT decision_receipt_result_domain_sequence_check;

-- A late decision never inserts a decision row, so the receipt's foreign
-- key into the decision table cannot apply to ignored-late receipts.
ALTER TABLE decision_receipt DROP CONSTRAINT decision_receipt_route_id_decision_id_fkey;
