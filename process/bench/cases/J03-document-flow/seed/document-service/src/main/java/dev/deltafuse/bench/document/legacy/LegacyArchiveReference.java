package dev.deltafuse.bench.document.legacy;

import java.time.Year;

/** Pointer to a box in the physical archive that the old pipeline produced. */
public record LegacyArchiveReference(String boxBarcode, Year depositYear, String warehouseCode) {

    public boolean needsDigitization() {
        return depositYear.isBefore(Year.of(2015));
    }
}
