package dev.deltafuse.bench.contracts;

import java.util.Set;

/**
 * The single approval role of a baseline single-step route. The parallel
 * expert and registrar roles of the target flow are reserved for the target
 * Change intake and must not appear in baseline contracts.
 */
public enum ActorRole {
    APPROVER;

    public String wireName() {
        return name().toLowerCase(java.util.Locale.ROOT);
    }

    public static Set<String> vocabulary() {
        return Set.of(APPROVER.wireName());
    }

    public static ActorRole parse(String value) {
        for (ActorRole role : values()) {
            if (role.wireName().equals(value)) {
                return role;
            }
        }
        throw new ContractViolation(ErrorCode.INVALID_SCHEMA, "unknown actor role: " + value);
    }
}
