package dev.deltafuse.bench.contracts;

import java.util.LinkedHashMap;
import java.util.Map;

/** An immutable version was created for a document. Aggregate: document. */
public record VersionCreated(String documentId, String versionId, String content) implements Payload {

    private static final int MAX_CONTENT_LENGTH = 65536;

    public VersionCreated {
        Identifiers.require("document_id", documentId);
        Identifiers.require("version_id", versionId);
        Identifiers.requireText("content", content, MAX_CONTENT_LENGTH);
    }

    @Override
    public JsonObj toJson() {
        Map<String, JsonValue> members = new LinkedHashMap<>();
        members.put("document_id", new JsonStr(documentId));
        members.put("version_id", new JsonStr(versionId));
        members.put("content", new JsonStr(content));
        return JsonObj.of(members);
    }

    public static VersionCreated fromJson(JsonObj json) {
        json.requireClosed("document_id", "version_id", "content");
        return new VersionCreated(json.getString("document_id"), json.getString("version_id"),
                json.getString("content"));
    }
}
