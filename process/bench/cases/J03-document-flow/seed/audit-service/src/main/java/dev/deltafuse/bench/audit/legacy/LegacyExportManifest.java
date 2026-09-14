package dev.deltafuse.bench.audit.legacy;

import java.util.List;

/** Manifest of a retired audit export batch. */
public record LegacyExportManifest(String exportId, List<LegacyTrailPage> pages,
        String producedBy) {

    public LegacyExportManifest {
        pages = List.copyOf(pages);
    }

    public int lineCount() {
        return pages.stream().mapToInt(page -> page.lineHashes().size()).sum();
    }
}
