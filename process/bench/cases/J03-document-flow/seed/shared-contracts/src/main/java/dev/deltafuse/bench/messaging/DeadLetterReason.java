package dev.deltafuse.bench.messaging;

/** Closed public reason vocabulary for rejected baseline events. */
public enum DeadLetterReason {
    MALFORMED_JSON,
    INVALID_CONTRACT,
    UNSUPPORTED_EVENT
}
