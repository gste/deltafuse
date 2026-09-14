package dev.deltafuse.bench.audit.legacy;

import java.util.ArrayList;
import java.util.List;

/** Mapping between retired export pages and trail filters. */
public final class LegacyTrailMapper {

    private LegacyTrailMapper() {
    }

    public static List<LegacyTrailPage> matching(List<LegacyTrailPage> pages,
            LegacyTrailFilter filter) {
        List<LegacyTrailPage> result = new ArrayList<>();
        for (LegacyTrailPage page : pages) {
            if (!page.complete()) {
                continue;
            }
            boolean any = false;
            for (String hash : page.lineHashes()) {
                if (filter.matches(hash)) {
                    any = true;
                    break;
                }
            }
            if (any) {
                result.add(page);
            }
        }
        return result;
    }
}
