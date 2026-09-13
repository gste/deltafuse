package dev.deltafuse.bench.contracts;

import java.math.BigDecimal;
import java.time.Instant;

public record RawMeasurement(
        String measurementId,
        String sensorId,
        Instant capturedAt,
        BigDecimal rawValue,
        String metadata) {
}
