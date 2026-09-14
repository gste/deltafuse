package dev.deltafuse.bench.audit.legacy;

/** Format sniffing of the retired export loader. */
public enum LegacyFormatDetector {
    INSTANCE;

    public String detect(String fileName) {
        if (fileName.endsWith(".zip")) {
            return "archive";
        }
        if (fileName.endsWith(".csv")) {
            return "delimited";
        }
        return "unknown";
    }
}
