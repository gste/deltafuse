package dev.deltafuse.bench.document.legacy;

/** Checksummed barcode of the retired label printer. */
public record LegacyBarcodeLabel(String payload, int checksum) {

    public static LegacyBarcodeLabel of(String payload) {
        int sum = 0;
        for (int i = 0; i < payload.length(); i++) {
            sum = (sum * 31 + payload.charAt(i)) % 97;
        }
        return new LegacyBarcodeLabel(payload, sum);
    }

    public boolean valid() {
        return LegacyBarcodeLabel.of(payload).checksum == checksum;
    }
}
