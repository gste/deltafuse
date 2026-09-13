package dev.deltafuse.bench.contracts;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Set;
import org.junit.jupiter.api.Test;

class EventSchemasTest {

    private static final Set<String> BASELINE_CATALOG = Set.of(
            "j03.document.created",
            "j03.document.version-created",
            "j03.document.version-submitted",
            "j03.workflow.route-created",
            "j03.workflow.decision-applied");

    @Test
    void known_names_are_exactly_the_baseline_catalog() {
        assertEquals(BASELINE_CATALOG, EventSchemas.knownNames());
        for (String name : BASELINE_CATALOG) {
            assertTrue(EventSchemas.knownVersions(name).contains(1));
        }
    }

    @Test
    void unknown_schema_name_is_rejected() {
        ContractViolation violation = assertThrows(ContractViolation.class,
                () -> EventSchemas.decodePayload("j03.workflow.route-superseded", 1, JsonValue.obj()));
        assertEquals(ErrorCode.INVALID_SCHEMA, violation.code());
    }

    @Test
    void unknown_schema_version_is_rejected() {
        ContractViolation violation = assertThrows(ContractViolation.class,
                () -> EventSchemas.decodePayload("j03.document.created", 2, JsonValue.obj()));
        assertEquals(ErrorCode.INVALID_SCHEMA, violation.code());
    }

    @Test
    void baseline_vocabulary_encodes_no_target_multi_stage_transition() {
        for (String name : EventSchemas.knownNames()) {
            assertFalse(name.contains("supersede"), name);
            assertFalse(name.contains("expert"), name);
            assertFalse(name.contains("registrar"), name);
        }
        assertEquals(Set.of("approver"), ActorRole.vocabulary());
        assertEquals(Set.of("APPROVE", "REJECT"), DecisionAction.vocabulary());
        assertEquals(Set.of("PENDING", "APPROVED", "REJECTED"), RouteState.vocabulary());
        assertThrows(IllegalArgumentException.class, () -> RouteState.valueOf("SUPERSEDED"));
        assertThrows(IllegalArgumentException.class, () -> ErrorCode.valueOf("ACTOR_ROLE_MISMATCH"));
        assertThrows(IllegalArgumentException.class, () -> ErrorCode.valueOf("EXPERT_REVIEW_INCOMPLETE"));
    }

    @Test
    void decode_dispatches_to_the_typed_payload() {
        JsonObj payload = CanonicalJson.parse(
                "{\"document_id\":\"doc-1\",\"title\":\"Policy\"}").asObj();
        Payload decoded = EventSchemas.decodePayload("j03.document.created", 1, payload);
        assertInstanceOf(DocumentCreated.class, decoded);
        assertEquals("doc-1", ((DocumentCreated) decoded).documentId());
    }
}
