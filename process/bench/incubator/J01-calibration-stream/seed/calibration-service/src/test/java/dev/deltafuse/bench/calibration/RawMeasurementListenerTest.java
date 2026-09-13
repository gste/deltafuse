package dev.deltafuse.bench.calibration;

import dev.deltafuse.bench.contracts.RawMeasurement;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Instant;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class RawMeasurementListenerTest {
    @Test
    void storesMeasurementWithIdentityCalibration() {
        MeasurementRepository repository = mock(MeasurementRepository.class);
        RawMeasurementListener listener = new RawMeasurementListener(repository);
        RawMeasurement measurement = new RawMeasurement(
                "m-1", "sensor-a", Instant.parse("2026-01-01T00:00:00Z"),
                new BigDecimal("12.500"), "baseline");

        listener.accept(measurement);

        verify(repository).storeIdentity(measurement);
    }
}
