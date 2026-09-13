package dev.deltafuse.bench.contracts;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * A valid decision was applied to a pending baseline route, closing it
 * exactly once. The payload binds the full identity tuple
 * ({@code document_id, version_id, route_id}) plus the idempotency key
 * {@code decision_id}, the acting identity, the claimed role and the action.
 * The resulting state is derived from the action, never an independent
 * claim. Aggregate: route.
 */
public record DecisionApplied(
        String documentId,
        String versionId,
        String routeId,
        String decisionId,
        String actorId,
        ActorRole role,
        DecisionAction action) implements Payload {

    public DecisionApplied {
        Identifiers.require("document_id", documentId);
        Identifiers.require("version_id", versionId);
        Identifiers.require("route_id", routeId);
        Identifiers.require("decision_id", decisionId);
        Identifiers.require("actor_id", actorId);
        java.util.Objects.requireNonNull(role, "role");
        java.util.Objects.requireNonNull(action, "action");
    }

    public RouteState resultingState() {
        return action == DecisionAction.APPROVE ? RouteState.APPROVED : RouteState.REJECTED;
    }

    @Override
    public JsonObj toJson() {
        Map<String, JsonValue> members = new LinkedHashMap<>();
        members.put("document_id", new JsonStr(documentId));
        members.put("version_id", new JsonStr(versionId));
        members.put("route_id", new JsonStr(routeId));
        members.put("decision_id", new JsonStr(decisionId));
        members.put("actor_id", new JsonStr(actorId));
        members.put("role", new JsonStr(role.wireName()));
        members.put("action", new JsonStr(action.name()));
        members.put("resulting_state", new JsonStr(resultingState().name()));
        return JsonObj.of(members);
    }

    public static DecisionApplied fromJson(JsonObj json) {
        json.requireClosed("document_id", "version_id", "route_id", "decision_id",
                "actor_id", "role", "action", "resulting_state");
        DecisionApplied decoded = new DecisionApplied(
                json.getString("document_id"),
                json.getString("version_id"),
                json.getString("route_id"),
                json.getString("decision_id"),
                json.getString("actor_id"),
                ActorRole.parse(json.getString("role")),
                DecisionAction.parse(json.getString("action")));
        if (!decoded.resultingState().name().equals(json.getString("resulting_state"))) {
            throw new ContractViolation(ErrorCode.INVALID_SCHEMA,
                    "resulting_state does not follow from action");
        }
        return decoded;
    }
}
