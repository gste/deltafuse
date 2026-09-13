package dev.deltafuse.bench.contracts;

import java.util.Map;
import java.util.Set;
import java.util.function.Function;

/**
 * Closed registry of baseline event schemas. A message decodes only when its
 * schema name and version are registered; everything else — including any
 * target-change schema such as a supersede transition — is
 * {@link ErrorCode#INVALID_SCHEMA} and never a transition.
 */
public final class EventSchemas {

    /** The only schema version of the baseline contracts. */
    public static final int BASELINE_VERSION = 1;

    private static final Map<String, Integer> SCHEMAS = Map.of(
            "j03.document.created", 1,
            "j03.document.version-created", 1,
            "j03.document.version-submitted", 1,
            "j03.workflow.route-created", 1,
            "j03.workflow.decision-applied", 1);

    private EventSchemas() {
    }

    public static Set<String> knownNames() {
        return SCHEMAS.keySet();
    }

    public static Set<Integer> knownVersions(String schemaName) {
        return SCHEMAS.containsKey(schemaName) ? Set.of(BASELINE_VERSION) : Set.of();
    }

    public static boolean isKnown(String schemaName, int schemaVersion) {
        return SCHEMAS.getOrDefault(schemaName, -1) == schemaVersion;
    }

    /** Decodes and validates a payload against its registered schema. */
    public static Payload decodePayload(String schemaName, int schemaVersion, JsonObj payload) {
        if (!isKnown(schemaName, schemaVersion)) {
            throw new ContractViolation(ErrorCode.INVALID_SCHEMA,
                    "unknown event schema: " + schemaName + "@" + schemaVersion);
        }
        return DECODERS.get(schemaName).apply(payload);
    }

    private static final Map<String, Function<JsonObj, Payload>> DECODERS = Map.of(
            "j03.document.created", DocumentCreated::fromJson,
            "j03.document.version-created", VersionCreated::fromJson,
            "j03.document.version-submitted", VersionSubmitted::fromJson,
            "j03.workflow.route-created", RouteCreated::fromJson,
            "j03.workflow.decision-applied", DecisionApplied::fromJson);
}
