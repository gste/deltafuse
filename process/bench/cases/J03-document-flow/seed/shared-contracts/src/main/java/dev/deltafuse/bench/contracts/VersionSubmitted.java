package dev.deltafuse.bench.contracts;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * A version was submitted for review. In the baseline this opens one
 * single-step route; route supersede semantics are reserved for the target
 * Change. Aggregate: document.
 */
public record VersionSubmitted(String documentId, String versionId) implements Payload {

    public VersionSubmitted {
        Identifiers.require("document_id", documentId);
        Identifiers.require("version_id", versionId);
    }

    @Override
    public JsonObj toJson() {
        Map<String, JsonValue> members = new LinkedHashMap<>();
        members.put("document_id", new JsonStr(documentId));
        members.put("version_id", new JsonStr(versionId));
        return JsonObj.of(members);
    }

    public static VersionSubmitted fromJson(JsonObj json) {
        json.requireClosed("document_id", "version_id");
        return new VersionSubmitted(json.getString("document_id"), json.getString("version_id"));
    }
}
