package dev.deltafuse.bench.workflow.legacy;

/** Escalation rule of the retired paper routing table. */
public record LegacyEscalationRule(int afterDays, String escalateToRole,
        boolean notifyDepartmentHead) {

    public LegacyEscalationRule {
        if (afterDays <= 0) {
            throw new IllegalArgumentException("afterDays must be positive");
        }
    }
}
