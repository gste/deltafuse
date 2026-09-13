package dev.deltafuse.bench.contracts;

import java.time.Instant;
import java.time.format.DateTimeParseException;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

/**
 * Immutable delivery envelope shared by every baseline event. It binds the
 * schema identity, unique event identity, producer, aggregate sequence and
 * the correlation/causation chain. Ordering is
 * {@code (domain_sequence, event_id)}; timestamps are diagnostic only.
 *
 * @param schemaName     closed schema name registered in {@link EventSchemas}
 * @param schemaVersion  integer schema version, 1 for the whole baseline
 * @param eventId        globally unique delivery identity
 * @param producer       producing service identity
 * @param aggregateType  aggregate kind owning the domain sequence
 * @param aggregateId    opaque aggregate identity
 * @param domainSequence monotonic sequence within the aggregate, starting at 1
 * @param correlationId  identity of the originating operation chain
 * @param causationId    event identity of the direct cause, null for a chain root
 * @param occurredAt     diagnostic ISO-8601 instant, null when unrecorded
 */
public record EventEnvelope(
        String schemaName,
        int schemaVersion,
        String eventId,
        String producer,
        AggregateType aggregateType,
        String aggregateId,
        long domainSequence,
        String correlationId,
        String causationId,
        String occurredAt) implements JsonWritable {

    public static final Comparator<EventEnvelope> DOMAIN_ORDER =
            Comparator.comparingLong(EventEnvelope::domainSequence).thenComparing(EventEnvelope::eventId);

    public EventEnvelope {
        Identifiers.require("schema_name", schemaName);
        if (schemaVersion < 1) {
            throw new ContractViolation(ErrorCode.INVALID_SCHEMA, "schema_version must be >= 1");
        }
        Identifiers.require("event_id", eventId);
        Identifiers.require("producer", producer);
        Objects.requireNonNull(aggregateType, "aggregate_type");
        Identifiers.require("aggregate_id", aggregateId);
        if (domainSequence < 1) {
            throw new ContractViolation(ErrorCode.INVALID_SCHEMA, "domain_sequence must be >= 1");
        }
        Identifiers.require("correlation_id", correlationId);
        if (causationId != null) {
            Identifiers.require("causation_id", causationId);
        }
        if (occurredAt != null) {
            try {
                Instant.parse(occurredAt);
            } catch (DateTimeParseException e) {
                throw new ContractViolation(ErrorCode.INVALID_SCHEMA, "occurred_at must be an ISO-8601 instant");
            }
        }
    }

    @Override
    public JsonObj toJson() {
        Map<String, JsonValue> members = new LinkedHashMap<>();
        members.put("schema_name", new JsonStr(schemaName));
        members.put("schema_version", new JsonNum(schemaVersion));
        members.put("event_id", new JsonStr(eventId));
        members.put("producer", new JsonStr(producer));
        members.put("aggregate_type", new JsonStr(aggregateType.name()));
        members.put("aggregate_id", new JsonStr(aggregateId));
        members.put("domain_sequence", new JsonNum(domainSequence));
        members.put("correlation_id", new JsonStr(correlationId));
        members.put("causation_id", causationId == null ? JsonNull.INSTANCE : new JsonStr(causationId));
        members.put("occurred_at", occurredAt == null ? JsonNull.INSTANCE : new JsonStr(occurredAt));
        return JsonObj.of(members);
    }

    public static EventEnvelope fromJson(JsonObj json) {
        json.requireClosed("schema_name", "schema_version", "event_id", "producer",
                "aggregate_type", "aggregate_id", "domain_sequence", "correlation_id",
                "causation_id", "occurred_at");
        return new EventEnvelope(
                json.getString("schema_name"),
                (int) json.getLong("schema_version"),
                json.getString("event_id"),
                json.getString("producer"),
                AggregateType.parse(json.getString("aggregate_type")),
                json.getString("aggregate_id"),
                json.getLong("domain_sequence"),
                json.getString("correlation_id"),
                json.getOptionalString("causation_id"),
                json.getOptionalString("occurred_at"));
    }
}
