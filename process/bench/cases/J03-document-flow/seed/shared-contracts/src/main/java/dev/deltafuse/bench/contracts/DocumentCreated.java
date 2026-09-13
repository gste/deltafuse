package dev.deltafuse.bench.contracts;

import java.util.LinkedHashMap;
import java.util.Map;

/** A draft document was created. Aggregate: document. */
public record DocumentCreated(String documentId, String title) implements Payload {

    private static final int MAX_TITLE_LENGTH = 512;

    public DocumentCreated {
        Identifiers.require("document_id", documentId);
        Identifiers.requireText("title", title, MAX_TITLE_LENGTH);
    }

    @Override
    public JsonObj toJson() {
        Map<String, JsonValue> members = new LinkedHashMap<>();
        members.put("document_id", new JsonStr(documentId));
        members.put("title", new JsonStr(title));
        return JsonObj.of(members);
    }

    public static DocumentCreated fromJson(JsonObj json) {
        json.requireClosed("document_id", "title");
        return new DocumentCreated(json.getString("document_id"), json.getString("title"));
    }
}
