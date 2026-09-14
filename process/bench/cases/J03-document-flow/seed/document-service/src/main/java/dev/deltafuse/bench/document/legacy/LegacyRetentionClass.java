package dev.deltafuse.bench.document.legacy;

import java.time.Year;

/** Retention classes of the retired records-management policy. */
public enum LegacyRetentionClass {
    SHORT(7), STANDARD(10), FISCAL(11), PERMANENT(-1);

    private final int years;

    LegacyRetentionClass(int years) {
        this.years = years;
    }

    public Year disposeAfter(Year deposit) {
        if (years < 0) {
            return Year.of(999_999_999);
        }
        return deposit.plusYears(years);
    }
}
