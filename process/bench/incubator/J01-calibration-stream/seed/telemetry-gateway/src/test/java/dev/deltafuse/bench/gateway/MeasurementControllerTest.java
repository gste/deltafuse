package dev.deltafuse.bench.gateway;

import dev.deltafuse.bench.contracts.RawMeasurement;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Instant;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class MeasurementControllerTest {
    @Test
    void publishesValidMeasurement() {
        MeasurementPublisher publisher = mock(MeasurementPublisher.class);
        MeasurementController controller = new MeasurementController(publisher);
        RawMeasurement measurement = new RawMeasurement(
                "m-1", "sensor-a", Instant.parse("2026-01-01T00:00:00Z"),
                new BigDecimal("12.500"), "baseline");

        assertEquals(202, controller.accept(measurement).getStatusCode().value());
        verify(publisher).publish(measurement);
    }
}
