package dev.deltafuse.bench.workflow.legacy;

import java.time.LocalDate;

/** Delegation of signature authority under the retired process. */
public record LegacyDelegationGrant(String fromReviewer, String toReviewer,
        LocalDate validFrom, LocalDate validTo) {

    public boolean covers(LocalDate date) {
        return !date.isBefore(validFrom) && !date.isAfter(validTo);
    }
}
