package dev.deltafuse.bench.workflow.legacy;

/** Rubber stamp codes of the retired circulation desk. */
public enum LegacyStampCode {
    FILED, RETURNED, DESTROYED, ARCHIVED;

    public boolean terminal() {
        return this == DESTROYED || this == ARCHIVED;
    }
}
