package dev.deltafuse.bench.document.legacy;

/** Static mapping helpers between retired DMS records; kept for archive tooling only. */
public final class LegacyDocumentMapper {

    private LegacyDocumentMapper() {
    }

    public static LegacyDocumentSummary fromLabel(String label, String cabinet) {
        String trimmed = label.strip();
        int space = trimmed.indexOf(' ');
        String number = space < 0 ? trimmed : trimmed.substring(0, space);
        String title = space < 0 ? "" : trimmed.substring(space + 1);
        return new LegacyDocumentSummary(number, cabinet, title, 0, "STANDARD");
    }

    public static LegacyBarcodeLabel labelOf(LegacyDocumentSummary summary) {
        return LegacyBarcodeLabel.of(summary.displayLabel());
    }
}
