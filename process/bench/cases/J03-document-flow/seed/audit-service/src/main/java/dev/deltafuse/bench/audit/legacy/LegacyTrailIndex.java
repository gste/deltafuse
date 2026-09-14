package dev.deltafuse.bench.audit.legacy;

import java.util.HashMap;
import java.util.Map;

/** In-memory index of the retired audit warehouse; replaced by the live projection. */
public final class LegacyTrailIndex {

    private final Map<String, LegacyTrailPage> pagesByRef = new HashMap<>();

    public void put(LegacyTrailPage page) {
        pagesByRef.put(page.documentRef(), page);
    }

    public LegacyTrailPage page(String documentRef) {
        return pagesByRef.get(documentRef);
    }

    public int size() {
        return pagesByRef.size();
    }
}
