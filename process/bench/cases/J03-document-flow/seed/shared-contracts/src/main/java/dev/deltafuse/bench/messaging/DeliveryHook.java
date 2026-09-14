package dev.deltafuse.bench.messaging;

@FunctionalInterface
public interface DeliveryHook {
    DeliveryHook NONE = barrier -> { };
    void reached(DeliveryBarrier barrier);
}
