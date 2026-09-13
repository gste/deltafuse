package dev.deltafuse.bench.contracts;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.function.Supplier;
import org.junit.jupiter.api.Test;

class EventEnvelopeTest {

    private EventEnvelope valid() {
        return new EventEnvelope(
                "j03.document.created", 1, "evt-1", "document-service",
                AggregateType.DOCUMENT, "doc-1", 1L, "op-1", null, null);
    }

    @Test
    void valid_envelope_round_trips_through_canonical_json() {
        EventEnvelope envelope = valid();
        JsonObj json = envelope.toJson();
        assertEquals(envelope, EventEnvelope.fromJson(json));
        assertEquals(envelope, EventEnvelope.fromJson(CanonicalJson.parse(CanonicalJson.write(json)).asObj()));
    }

    @Test
    void missing_or_empty_identity_is_rejected() {
        assertEquals(ErrorCode.INVALID_SCHEMA, violationCode(() -> new EventEnvelope(
                "j03.document.created", 1, "", "document-service",
                AggregateType.DOCUMENT, "doc-1", 1L, "op-1", null, null)));
        assertEquals(ErrorCode.INVALID_SCHEMA, violationCode(() -> new EventEnvelope(
                "j03.document.created", 1, "evt-1", "document-service",
                AggregateType.DOCUMENT, null, 1L, "op-1", null, null)));
        assertEquals(ErrorCode.INVALID_SCHEMA, violationCode(() -> new EventEnvelope(
                "j03.document.created", 1, "evt-1", "document-service",
                AggregateType.DOCUMENT, "doc-1", 1L, "", null, null)));
    }

    @Test
    void non_positive_sequence_or_version_is_rejected() {
        assertEquals(ErrorCode.INVALID_SCHEMA, violationCode(() -> new EventEnvelope(
                "j03.document.created", 1, "evt-1", "document-service",
                AggregateType.DOCUMENT, "doc-1", 0L, "op-1", null, null)));
        assertEquals(ErrorCode.INVALID_SCHEMA, violationCode(() -> new EventEnvelope(
                "j03.document.created", 0, "evt-1", "document-service",
                AggregateType.DOCUMENT, "doc-1", 1L, "op-1", null, null)));
    }

    @Test
    void control_characters_and_oversized_ids_are_rejected() {
        assertEquals(ErrorCode.INVALID_SCHEMA, violationCode(() -> new EventEnvelope(
                "j03.document.created", 1, "evt\u0000-1", "document-service",
                AggregateType.DOCUMENT, "doc-1", 1L, "op-1", null, null)));
        assertEquals(ErrorCode.INVALID_SCHEMA, violationCode(() -> new EventEnvelope(
                "j03.document.created", 1, "e".repeat(129), "document-service",
                AggregateType.DOCUMENT, "doc-1", 1L, "op-1", null, null)));
    }

    @Test
    void unknown_aggregate_type_is_rejected() {
        assertThrows(ContractViolation.class, () -> AggregateType.parse("workflow-v2"));
    }

    @Test
    void diagnostic_timestamp_must_be_iso_8601() {
        assertEquals(ErrorCode.INVALID_SCHEMA, violationCode(() -> new EventEnvelope(
                "j03.document.created", 1, "evt-1", "document-service",
                AggregateType.DOCUMENT, "doc-1", 1L, "op-1", null, "not-a-time")));
    }

    @Test
    void domain_order_is_sequence_then_event_id_ignoring_timestamps() {
        EventEnvelope a = new EventEnvelope("j03.document.created", 1, "evt-a", "p",
                AggregateType.DOCUMENT, "doc-1", 2L, "op", null, "2026-01-01T00:00:09Z");
        EventEnvelope b = new EventEnvelope("j03.document.created", 1, "evt-b", "p",
                AggregateType.DOCUMENT, "doc-1", 2L, "op", null, "2026-01-01T00:00:01Z");
        EventEnvelope c = new EventEnvelope("j03.document.created", 1, "evt-c", "p",
                AggregateType.DOCUMENT, "doc-1", 3L, "op", null, "2026-01-01T00:00:05Z");
        List<EventEnvelope> ordered = List.of(c, b, a).stream().sorted(EventEnvelope.DOMAIN_ORDER).toList();
        assertEquals(List.of(a, b, c), ordered);
        assertTrue(EventEnvelope.DOMAIN_ORDER.compare(b, a) > 0);
    }

    private ErrorCode violationCode(Supplier<EventEnvelope> construction) {
        ContractViolation violation = assertThrows(ContractViolation.class, construction::get);
        return violation.code();
    }
}
