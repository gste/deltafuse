package dev.deltafuse.bench.audit.legacy;

/** Checksum record of the retired export verifier. */
public record LegacyChecksumRecord(String exportId, String sha256Hex,
        long byteLength) {

    public boolean plausible() {
        return sha256Hex != null && sha256Hex.length() == 64 && byteLength >= 0;
    }
}
