package dev.deltafuse.bench.workflow.legacy;

/** Signature specimen card of the retired reviewer registry. */
public record LegacySignatureCard(String reviewerName, String specimenCode,
        boolean stillEmployed) {

    public boolean current() {
        return stillEmployed;
    }
}
