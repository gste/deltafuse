package dev.deltafuse.bench.workflow.legacy;

/** Decision codes of the retired paper process. */
public enum LegacyDecisionCode {
    AGREE, AGREE_WITH_NOTES, DISAGREE, ABSTAIN;

    public boolean blocksFiling() {
        return this == DISAGREE;
    }
}
