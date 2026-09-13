package dev.deltafuse.bench.contracts;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * A single-step route opened with exactly one assigned approver. Aggregate:
 * route.
 */
public record RouteCreated(
        String documentId,
        String versionId,
        String routeId,
        String approverActorId) implements Payload {

    public RouteCreated {
        Identifiers.require("document_id", documentId);
        Identifiers.require("version_id", versionId);
        Identifiers.require("route_id", routeId);
        Identifiers.require("approver_actor_id", approverActorId);
    }

    @Override
    public JsonObj toJson() {
        Map<String, JsonValue> members = new LinkedHashMap<>();
        members.put("document_id", new JsonStr(documentId));
        members.put("version_id", new JsonStr(versionId));
        members.put("route_id", new JsonStr(routeId));
        members.put("approver_actor_id", new JsonStr(approverActorId));
        return JsonObj.of(members);
    }

    public static RouteCreated fromJson(JsonObj json) {
        json.requireClosed("document_id", "version_id", "route_id", "approver_actor_id");
        return new RouteCreated(json.getString("document_id"), json.getString("version_id"),
                json.getString("route_id"), json.getString("approver_actor_id"));
    }
}
