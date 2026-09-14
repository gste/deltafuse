-- Private J03-304 reference extension: legal/security then registrar.
ALTER TABLE decision DROP CONSTRAINT IF EXISTS decision_role_check;
ALTER TABLE decision ADD CONSTRAINT decision_role_check
    CHECK (role IN ('legal', 'security', 'registrar'));
ALTER TABLE decision DROP CONSTRAINT IF EXISTS decision_resulting_state_check;
ALTER TABLE decision ADD CONSTRAINT decision_resulting_state_check
    CHECK (resulting_state IN ('PENDING', 'APPROVED', 'REJECTED'));
ALTER TABLE decision_receipt DROP CONSTRAINT decision_receipt_result_state_check;
ALTER TABLE decision_receipt ADD CONSTRAINT decision_receipt_result_state_check
    CHECK (result_state IN ('PENDING', 'APPROVED', 'REJECTED',
        'IGNORED_LATE_DECISION', 'IDENTITY_MISMATCH', 'ACTOR_ROLE_MISMATCH',
        'EXPERT_REVIEW_INCOMPLETE', 'UNSUPPORTED_ACTION'));
CREATE UNIQUE INDEX decision_one_role_per_route
    ON decision(route_id, role);
