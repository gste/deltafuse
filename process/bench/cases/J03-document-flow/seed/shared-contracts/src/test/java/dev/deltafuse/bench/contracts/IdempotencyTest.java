package dev.deltafuse.bench.contracts;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class IdempotencyTest {

    @Test
    void canonical_payload_equality_ignores_raw_member_order() {
        assertTrue(Idempotency.samePayload(
                "{\"decision_id\":\"d-1\",\"action\":\"APPROVE\"}",
                "{\"action\":\"APPROVE\",\"decision_id\":\"d-1\"}"));
    }

    @Test
    void identical_payload_replay_does_not_conflict() {
        assertDoesNotThrow(() -> Idempotency.requireSamePayload(
                "op-1", "{\"a\":1}", "{ \"a\" : 1 }"));
    }

    @Test
    void reused_key_with_different_payload_is_an_idempotency_conflict() {
        ContractViolation violation = assertThrows(ContractViolation.class,
                () -> Idempotency.requireSamePayload("op-1", "{\"a\":1}", "{\"a\":2}"));
        assertEquals(ErrorCode.IDEMPOTENCY_CONFLICT, violation.code());
    }

    @Test
    void malformed_payloads_cannot_be_compared() {
        assertThrows(IllegalArgumentException.class,
                () -> Idempotency.samePayload("{\"a\":1}", "{\"a\":"));
    }
}
