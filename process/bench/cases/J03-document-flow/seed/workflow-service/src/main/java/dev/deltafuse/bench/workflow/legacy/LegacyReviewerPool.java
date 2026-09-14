package dev.deltafuse.bench.workflow.legacy;

import java.util.List;

/** Reviewer pool of the retired assignment process. */
public record LegacyReviewerPool(String departmentCode, List<LegacySignatureCard> cards) {

    public LegacyReviewerPool {
        cards = List.copyOf(cards);
    }

    public List<LegacySignatureCard> currentReviewers() {
        return cards.stream().filter(LegacySignatureCard::current).toList();
    }
}
