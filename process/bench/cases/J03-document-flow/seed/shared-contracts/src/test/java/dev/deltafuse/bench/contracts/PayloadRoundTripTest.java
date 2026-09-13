package dev.deltafuse.bench.contracts;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

class PayloadRoundTripTest {

    private static JsonObj payload(String raw) {
        return CanonicalJson.parse(raw).asObj();
    }

    @Test
    void document_created_round_trips() {
        JsonObj json = payload("{\"document_id\":\"doc-1\",\"title\":\"Policy A\"}");
        DocumentCreated decoded = (DocumentCreated) EventSchemas.decodePayload("j03.document.created", 1, json);
        assertEquals("doc-1", decoded.documentId());
        assertEquals("Policy A", decoded.title());
        assertEquals(json, decoded.toJson());
    }

    @Test
    void version_created_and_submitted_round_trip() {
        VersionCreated created = (VersionCreated) EventSchemas.decodePayload("j03.document.version-created", 1,
                payload("{\"document_id\":\"doc-1\",\"version_id\":\"v-1\",\"content\":\"body\"}"));
        assertEquals("v-1", created.versionId());
        assertEquals(payload("{\"document_id\":\"doc-1\",\"version_id\":\"v-1\",\"content\":\"body\"}"),
                created.toJson());

        VersionSubmitted submitted = (VersionSubmitted) EventSchemas.decodePayload("j03.document.version-submitted", 1,
                payload("{\"document_id\":\"doc-1\",\"version_id\":\"v-1\"}"));
        assertEquals("doc-1", submitted.documentId());
        assertEquals(payload("{\"document_id\":\"doc-1\",\"version_id\":\"v-1\"}"), submitted.toJson());
    }

    @Test
    void route_created_binds_the_single_approver() {
        RouteCreated route = (RouteCreated) EventSchemas.decodePayload("j03.workflow.route-created", 1, payload(
                "{\"document_id\":\"doc-1\",\"version_id\":\"v-1\",\"route_id\":\"r-1\",\"approver_actor_id\":\"usr-9\"}"));
        assertEquals("usr-9", route.approverActorId());
        assertEquals(payload(
                "{\"approver_actor_id\":\"usr-9\",\"document_id\":\"doc-1\",\"route_id\":\"r-1\",\"version_id\":\"v-1\"}"),
                route.toJson());
    }

    @Test
    void decision_applied_binds_identity_action_and_resulting_state() {
        DecisionApplied approve = (DecisionApplied) EventSchemas.decodePayload("j03.workflow.decision-applied", 1,
                payload("{\"action\":\"APPROVE\",\"actor_id\":\"usr-9\",\"decision_id\":\"d-1\","
                        + "\"document_id\":\"doc-1\",\"resulting_state\":\"APPROVED\",\"role\":\"approver\","
                        + "\"route_id\":\"r-1\",\"version_id\":\"v-1\"}"));
        assertEquals(DecisionAction.APPROVE, approve.action());
        assertEquals(ActorRole.APPROVER, approve.role());
        assertEquals(RouteState.APPROVED, approve.resultingState());
        assertEquals(payload("{\"action\":\"APPROVE\",\"actor_id\":\"usr-9\",\"decision_id\":\"d-1\","
                + "\"document_id\":\"doc-1\",\"resulting_state\":\"APPROVED\",\"role\":\"approver\","
                + "\"route_id\":\"r-1\",\"version_id\":\"v-1\"}"), approve.toJson());

        DecisionApplied reject = new DecisionApplied("doc-1", "v-1", "r-1", "d-2", "usr-9",
                ActorRole.APPROVER, DecisionAction.REJECT);
        assertEquals(RouteState.REJECTED, reject.resultingState());
    }

    @Test
    void unknown_payload_field_is_rejected() {
        ContractViolation violation = assertThrows(ContractViolation.class,
                () -> EventSchemas.decodePayload("j03.document.created", 1,
                        payload("{\"document_id\":\"doc-1\",\"title\":\"A\",\"extra\":1}")));
        assertEquals(ErrorCode.INVALID_SCHEMA, violation.code());
    }

    @Test
    void missing_required_payload_field_is_rejected() {
        ContractViolation violation = assertThrows(ContractViolation.class,
                () -> EventSchemas.decodePayload("j03.document.created", 1, payload("{\"document_id\":\"doc-1\"}")));
        assertEquals(ErrorCode.INVALID_SCHEMA, violation.code());
    }

    @Test
    void wrong_field_type_is_rejected() {
        assertThrows(ContractViolation.class, () -> EventSchemas.decodePayload("j03.document.created", 1,
                payload("{\"document_id\":\"doc-1\",\"title\":true}")));
        assertThrows(ContractViolation.class, () -> EventSchemas.decodePayload("j03.document.created", 1,
                payload("{\"document_id\":7,\"title\":\"A\"}")));
    }

    @Test
    void empty_or_control_payload_identity_is_rejected() {
        assertThrows(ContractViolation.class, () -> EventSchemas.decodePayload("j03.document.created", 1,
                payload("{\"document_id\":\"\",\"title\":\"A\"}")));
        assertThrows(ContractViolation.class, () -> EventSchemas.decodePayload("j03.document.created", 1,
                payload("{\"document_id\":\"doc\\u0007-1\",\"title\":\"A\"}")));
    }

    @Test
    void unsupported_action_is_retained_as_invalid_not_a_transition() {
        ContractViolation violation =
                assertThrows(ContractViolation.class, () -> DecisionAction.parse("ESCALATE"));
        assertEquals(ErrorCode.UNSUPPORTED_ACTION, violation.code());
    }

    @Test
    void target_roles_are_not_in_the_baseline_vocabulary() {
        assertThrows(ContractViolation.class, () -> ActorRole.parse("registrar"));
        assertThrows(ContractViolation.class, () -> ActorRole.parse("legal"));
        assertThrows(ContractViolation.class, () -> ActorRole.parse("security"));
    }

    @Test
    void oversized_payload_text_is_rejected() {
        assertThrows(ContractViolation.class, () -> EventSchemas.decodePayload("j03.document.created", 1,
                payload("{\"document_id\":\"doc-1\",\"title\":\"" + "x".repeat(513) + "\"}")));
    }
}
