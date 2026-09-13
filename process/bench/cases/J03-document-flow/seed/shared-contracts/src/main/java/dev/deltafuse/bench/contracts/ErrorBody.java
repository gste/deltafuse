package dev.deltafuse.bench.contracts;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.SortedMap;
import java.util.TreeMap;

/**
 * Public error body {@code {code, operation_id, details}} of the baseline
 * API. Prose messages are never part of a scored assertion; the code and the
 * stable result identity are.
 */
public record ErrorBody(ErrorCode code, String operationId, Map<String, String> details) implements JsonWritable {

    public ErrorBody {
        java.util.Objects.requireNonNull(code, "code");
        Identifiers.require("operation_id", operationId);
        SortedMap<String, String> sorted = new TreeMap<>(details);
        for (Map.Entry<String, String> entry : sorted.entrySet()) {
            Identifiers.require("details key", entry.getKey());
            java.util.Objects.requireNonNull(entry.getValue(), "details value");
        }
        details = Collections.unmodifiableSortedMap(sorted);
    }

    public int httpStatus() {
        return code.httpStatus();
    }

    @Override
    public JsonObj toJson() {
        Map<String, JsonValue> detailMembers = new TreeMap<>();
        details.forEach((key, value) -> detailMembers.put(key, new JsonStr(value)));
        Map<String, JsonValue> members = new LinkedHashMap<>();
        members.put("code", new JsonStr(code.name()));
        members.put("operation_id", new JsonStr(operationId));
        members.put("details", JsonObj.of(detailMembers));
        return JsonObj.of(members);
    }

    public static ErrorBody fromJson(JsonObj json) {
        json.requireClosed("code", "operation_id", "details");
        ErrorCode code = ErrorCode.parse(json.getString("code"));
        String operationId = json.getString("operation_id");
        JsonObj detailsJson = json.getObj("details");
        Map<String, String> details = new TreeMap<>();
        for (Map.Entry<String, JsonValue> entry : detailsJson.members().entrySet()) {
            if (!(entry.getValue() instanceof JsonStr str)) {
                throw new ContractViolation(ErrorCode.INVALID_SCHEMA,
                        "details values must be strings: " + entry.getKey());
            }
            details.put(entry.getKey(), str.value());
        }
        return new ErrorBody(code, operationId, details);
    }
}
