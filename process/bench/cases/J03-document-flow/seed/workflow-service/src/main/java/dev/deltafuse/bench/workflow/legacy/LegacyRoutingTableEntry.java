package dev.deltafuse.bench.workflow.legacy;

/** One row of the retired routing table. */
public record LegacyRoutingTableEntry(String documentKind, String firstRole,
        String secondRole, int slaDays) {

    public boolean twoStage() {
        return secondRole != null && !secondRole.isBlank();
    }
}
