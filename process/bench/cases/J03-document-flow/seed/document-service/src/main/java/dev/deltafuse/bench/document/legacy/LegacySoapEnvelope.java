package dev.deltafuse.bench.document.legacy;

import java.util.Map;

/** Envelope skeleton of the retired SOAP gateway, retained for archive replay. */
public record LegacySoapEnvelope(String action, Map<String, String> headers, String body) {

    public LegacySoapEnvelope {
        headers = Map.copyOf(headers);
    }

    public String header(String name) {
        return headers.get(name);
    }
}
