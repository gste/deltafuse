package dev.deltafuse.bench.document.legacy;

import java.time.Year;

/** Disposal date arithmetic of the retired records policy. */
public final class LegacyRetentionCalculator {

    private LegacyRetentionCalculator() {
    }

    public static Year disposeAfter(String retentionClassName, Year deposit) {
        LegacyRetentionClass retention = LegacyRetentionClass.valueOf(retentionClassName);
        return retention.disposeAfter(deposit);
    }

    public static boolean disposableIn(Year current, String retentionClassName, Year deposit) {
        return !current.isBefore(disposeAfter(retentionClassName, deposit));
    }
}
