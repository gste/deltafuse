package dev.deltafuse.bench.contracts;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Encode/decode facade for baseline events. The wire form is one canonical
 * JSON object containing the envelope members plus a closed {@code payload}
 * object typed by the registered schema.
 */
public final class BaselineEvents {

    private BaselineEvents() {
    }

    public static String encode(EventEnvelope envelope, JsonObj payload) {
        Map<String, JsonValue> members = new LinkedHashMap<>(envelope.toJson().members());
        members.put("payload", payload);
        return CanonicalJson.write(JsonObj.of(members));
    }

    public static String encode(Decoded decoded) {
        return encode(decoded.envelope(), decoded.payload().toJson());
    }

    public static Decoded decode(String json) {
        JsonValue parsed;
        try {
            parsed = CanonicalJson.parse(json);
        } catch (IllegalArgumentException e) {
            throw new ContractViolation(ErrorCode.INVALID_SCHEMA, "malformed event JSON: " + e.getMessage());
        }
        if (!(parsed instanceof JsonObj obj)) {
            throw new ContractViolation(ErrorCode.INVALID_SCHEMA, "event must be a JSON object");
        }
        obj.requireClosed("schema_name", "schema_version", "event_id", "producer",
                "aggregate_type", "aggregate_id", "domain_sequence", "correlation_id",
                "causation_id", "occurred_at", "payload");
        JsonValue payloadValue = obj.member("payload");
        if (!(payloadValue instanceof JsonObj payloadJson)) {
            throw new ContractViolation(ErrorCode.INVALID_SCHEMA, "event payload must be an object");
        }
        Map<String, JsonValue> envelopeMembers = new LinkedHashMap<>(obj.members());
        envelopeMembers.remove("payload");
        EventEnvelope envelope = EventEnvelope.fromJson(JsonObj.of(envelopeMembers));
        Payload payload = EventSchemas.decodePayload(envelope.schemaName(), envelope.schemaVersion(), payloadJson);
        return new Decoded(envelope, payload);
    }

    /**
     * A decoded baseline event: validated envelope plus typed payload.
     */
    public record Decoded(EventEnvelope envelope, Payload payload) {
    }
}
