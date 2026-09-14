package dev.deltafuse.bench.audit.legacy;

/** Filter of the retired audit export tool. */
public record LegacyTrailFilter(String kindPrefix, String dateFrom, String dateTo) {

    public boolean matches(String kind) {
        return kindPrefix == null || kindPrefix.isBlank() || kind.startsWith(kindPrefix);
    }
}
