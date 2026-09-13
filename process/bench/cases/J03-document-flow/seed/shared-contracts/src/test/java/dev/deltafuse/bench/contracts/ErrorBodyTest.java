package dev.deltafuse.bench.contracts;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.Map;
import org.junit.jupiter.api.Test;

class ErrorBodyTest {

    @Test
    void error_body_round_trips_with_sorted_details() {
        ErrorBody body = new ErrorBody(ErrorCode.IDEMPOTENCY_CONFLICT, "op-7",
                Map.of("binding", "decision_id", "operation", "submit"));
        ErrorBody decoded = ErrorBody.fromJson(body.toJson());
        assertEquals(body, decoded);
        assertEquals("{\"code\":\"IDEMPOTENCY_CONFLICT\",\"details\":{\"binding\":\"decision_id\","
                + "\"operation\":\"submit\"},\"operation_id\":\"op-7\"}",
                CanonicalJson.write(body.toJson()));
    }

    @Test
    void http_status_mapping_matches_the_published_contract() {
        assertEquals(400, ErrorCode.INVALID_SCHEMA.httpStatus());
        assertEquals(400, ErrorCode.IDENTITY_MISMATCH.httpStatus());
        assertEquals(400, ErrorCode.UNSUPPORTED_ACTION.httpStatus());
        assertEquals(404, ErrorCode.DOCUMENT_NOT_FOUND.httpStatus());
        assertEquals(404, ErrorCode.VERSION_NOT_FOUND.httpStatus());
        assertEquals(409, ErrorCode.VERSION_IMMUTABLE.httpStatus());
        assertEquals(409, ErrorCode.IDEMPOTENCY_CONFLICT.httpStatus());
        assertEquals(409, new ErrorBody(ErrorCode.VERSION_IMMUTABLE, "op-1", Map.of()).httpStatus());
    }

    @Test
    void unknown_error_code_string_is_rejected() {
        ContractViolation violation = assertThrows(ContractViolation.class,
                () -> ErrorBody.fromJson(CanonicalJson.parse(
                        "{\"code\":\"DISTRIBUTED_ROLLBACK\",\"operation_id\":\"op-1\",\"details\":{}}").asObj()));
        assertEquals(ErrorCode.INVALID_SCHEMA, violation.code());
    }

    @Test
    void operation_id_is_required_and_details_must_be_string_valued() {
        assertThrows(ContractViolation.class, () -> ErrorBody.fromJson(CanonicalJson.parse(
                "{\"code\":\"INVALID_SCHEMA\",\"details\":{}}").asObj()));
        assertThrows(ContractViolation.class, () -> ErrorBody.fromJson(CanonicalJson.parse(
                "{\"code\":\"INVALID_SCHEMA\",\"operation_id\":\"op-1\",\"details\":{\"k\":7}}").asObj()));
    }
}
