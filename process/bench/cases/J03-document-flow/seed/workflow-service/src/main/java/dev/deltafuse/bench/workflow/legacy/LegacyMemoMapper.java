package dev.deltafuse.bench.workflow.legacy;

/** Mapping between retired memo verdicts and decision codes. */
public final class LegacyMemoMapper {

    private LegacyMemoMapper() {
    }

    public static LegacyDecisionCode codeOf(LegacyApprovalMemo memo) {
        if (memo.verdictText() == null) {
            return LegacyDecisionCode.ABSTAIN;
        }
        String verdict = memo.verdictText().toLowerCase();
        if (verdict.startsWith("agree with")) {
            return LegacyDecisionCode.AGREE_WITH_NOTES;
        }
        if (verdict.startsWith("agree")) {
            return LegacyDecisionCode.AGREE;
        }
        if (verdict.startsWith("disagree")) {
            return LegacyDecisionCode.DISAGREE;
        }
        return LegacyDecisionCode.ABSTAIN;
    }
}
