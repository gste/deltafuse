package dev.deltafuse.bench.contracts;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;

class BaselineEventsTest {

    private EventEnvelope envelope(String schemaName, AggregateType aggregateType, String aggregateId) {
        return new EventEnvelope(schemaName, 1, "evt-1", "document-service",
                aggregateType, aggregateId, 1L, "op-1", null, "2026-09-13T00:00:00Z");
    }

    @Test
    void full_event_round_trip_is_byte_identical() {
        JsonObj payload = CanonicalJson.parse("{\"document_id\":\"doc-1\",\"title\":\"Policy A\"}").asObj();
        String encoded = BaselineEvents.encode(
                envelope("j03.document.created", AggregateType.DOCUMENT, "doc-1"), payload);
        BaselineEvents.Decoded decoded = BaselineEvents.decode(encoded);
        assertEquals("j03.document.created", decoded.envelope().schemaName());
        assertEquals("doc-1", ((DocumentCreated) decoded.payload()).documentId());
        assertEquals(encoded, BaselineEvents.encode(decoded.envelope(), decoded.payload().toJson()));
    }

    @Test
    void encoded_event_is_canonical_and_utf8() {
        JsonObj payload = CanonicalJson.parse("{\"document_id\":\"doc-1\",\"title\":\"Policy A\"}").asObj();
        String encoded = BaselineEvents.encode(
                envelope("j03.document.created", AggregateType.DOCUMENT, "doc-1"), payload);
        assertEquals(encoded, new String(encoded.getBytes(StandardCharsets.UTF_8), StandardCharsets.UTF_8));
        assertEquals('{', encoded.charAt(0));
        assertEquals(-1, encoded.indexOf(", "));
        assertEquals(-1, encoded.indexOf("\": {"));
    }

    @Test
    void target_flavored_schema_names_are_unknown_at_decode() {
        JsonObj payload = CanonicalJson.parse("{\"document_id\":\"doc-1\",\"title\":\"Policy A\"}").asObj();
        String forged = BaselineEvents.encode(
                envelope("j03.workflow.route-superseded", AggregateType.ROUTE, "r-1"), payload);
        ContractViolation violation = assertThrows(ContractViolation.class, () -> BaselineEvents.decode(forged));
        assertEquals(ErrorCode.INVALID_SCHEMA, violation.code());
    }

    @Test
    void missing_envelope_identity_fails_decode() {
        String raw = "{\"schema_name\":\"j03.document.created\",\"schema_version\":1,"
                + "\"producer\":\"document-service\",\"aggregate_type\":\"DOCUMENT\","
                + "\"aggregate_id\":\"doc-1\",\"domain_sequence\":1,\"correlation_id\":\"op-1\","
                + "\"payload\":{\"document_id\":\"doc-1\",\"title\":\"Policy A\"}}";
        ContractViolation violation = assertThrows(ContractViolation.class, () -> BaselineEvents.decode(raw));
        assertEquals(ErrorCode.INVALID_SCHEMA, violation.code());
    }

    @Test
    void malformed_json_fails_decode() {
        assertThrows(Exception.class, () -> BaselineEvents.decode("{\"schema_name\":"));
    }
}
