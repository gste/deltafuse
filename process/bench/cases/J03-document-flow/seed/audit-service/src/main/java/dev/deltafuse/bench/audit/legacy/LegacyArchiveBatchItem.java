package dev.deltafuse.bench.audit.legacy;

/** One item of the retired archive loader. */
public record LegacyArchiveBatchItem(String fileName, String checksum,
        LegacyRetentionFlag flag) {

    public boolean purgeCandidate() {
        return flag == LegacyRetentionFlag.PURGE_NEXT_RUN;
    }
}
