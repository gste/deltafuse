package dev.deltafuse.bench.workflow.legacy;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/** The retired routing table of the paper circulation desk. */
public final class LegacyRoutingTable {

    private final List<LegacyRoutingTableEntry> entries = new ArrayList<>();

    public void register(LegacyRoutingTableEntry entry) {
        entries.add(entry);
    }

    public Optional<LegacyRoutingTableEntry> forKind(String documentKind) {
        return entries.stream()
                .filter(entry -> entry.documentKind().equals(documentKind))
                .findFirst();
    }
}
