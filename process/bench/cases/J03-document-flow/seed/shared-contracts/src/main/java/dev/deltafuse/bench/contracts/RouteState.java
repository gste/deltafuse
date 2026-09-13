package dev.deltafuse.bench.contracts;

import java.util.Set;

/**
 * Baseline route states of the working single-step flow. A route closes
 * exactly once; supersede and other target states are reserved for the
 * target Change.
 */
public enum RouteState {
    PENDING,
    APPROVED,
    REJECTED;

    public static Set<String> vocabulary() {
        return Set.of(PENDING.name(), APPROVED.name(), REJECTED.name());
    }
}
