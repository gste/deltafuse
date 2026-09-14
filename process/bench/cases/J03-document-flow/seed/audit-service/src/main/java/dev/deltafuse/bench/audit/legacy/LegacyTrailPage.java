package dev.deltafuse.bench.audit.legacy;

import java.util.List;

/** One page of the retired audit export format. */
public record LegacyTrailPage(String documentRef, int pageIndex,
        List<String> lineHashes) {

    public LegacyTrailPage {
        lineHashes = List.copyOf(lineHashes);
    }

    public boolean complete() {
        return pageIndex >= 0 && !lineHashes.isEmpty();
    }
}
