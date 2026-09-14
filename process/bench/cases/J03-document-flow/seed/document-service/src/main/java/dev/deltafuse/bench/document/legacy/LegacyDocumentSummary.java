package dev.deltafuse.bench.document.legacy;

/** Summary card of the retired DMS import pipeline. Never wired into the live flow. */
public record LegacyDocumentSummary(String legacyNumber, String cabinetCode,
        String title, int pageCount, String retentionClass) {

    public LegacyDocumentSummary {
        if (legacyNumber == null || legacyNumber.isBlank()) {
            throw new IllegalArgumentException("legacyNumber is required");
        }
        pageCount = Math.max(0, pageCount);
    }

    public String displayLabel() {
        return cabinetCode + "/" + legacyNumber + " " + title;
    }
}
