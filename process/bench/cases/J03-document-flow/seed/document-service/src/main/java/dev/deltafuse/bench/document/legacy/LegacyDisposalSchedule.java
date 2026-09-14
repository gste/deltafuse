package dev.deltafuse.bench.document.legacy;

import java.time.Year;
import java.util.HashMap;
import java.util.Map;

/** Disposal schedule of the retired warehouse; consulted only by archive tooling. */
public final class LegacyDisposalSchedule {

    private final Map<String, Year> disposeByCabinet = new HashMap<>();

    public void schedule(String cabinet, Year disposeAfter) {
        disposeByCabinet.put(cabinet, disposeAfter);
    }

    public boolean disposable(String cabinet, Year today) {
        Year disposeAfter = disposeByCabinet.get(cabinet);
        return disposeAfter != null && !today.isBefore(disposeAfter);
    }
}
