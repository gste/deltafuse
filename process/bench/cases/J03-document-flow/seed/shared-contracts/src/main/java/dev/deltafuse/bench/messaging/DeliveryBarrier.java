package dev.deltafuse.bench.messaging;

/** Named fault points exposed only through injected test hooks. */
public enum DeliveryBarrier {
    AFTER_PUBLISH_BEFORE_SENT,
    AFTER_COMMIT_BEFORE_ACK
}
