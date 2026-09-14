package dev.deltafuse.bench.audit.legacy;

/** Retention flags of the retired audit warehouse. */
public enum LegacyRetentionFlag {
    KEEP_FOREVER, KEEP_10Y, KEEP_3Y, PURGE_NEXT_RUN
}
