package dev.deltafuse.bench.document.legacy;

import java.time.Instant;

/** Queue entry of the retired FTP importer. */
public record LegacyImportQueueItem(String fileName, long byteLength,
        Instant depositedAt, String targetCabinet) {

    public boolean oversized(long limit) {
        return byteLength > limit;
    }
}
