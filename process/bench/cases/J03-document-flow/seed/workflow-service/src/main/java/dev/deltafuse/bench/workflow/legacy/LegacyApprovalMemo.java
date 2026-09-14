package dev.deltafuse.bench.workflow.legacy;

/** Paper-era approval memo of the retired circulation process. */
public record LegacyApprovalMemo(String memoNumber, String reviewerName,
        String verdictText, String stampCode) {

    public boolean favourable() {
        return verdictText != null && verdictText.toLowerCase().startsWith("agree");
    }
}
