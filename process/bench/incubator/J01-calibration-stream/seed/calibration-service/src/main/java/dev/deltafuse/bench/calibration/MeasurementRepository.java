package dev.deltafuse.bench.calibration;

import dev.deltafuse.bench.contracts.RawMeasurement;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.Optional;

@Repository
public class MeasurementRepository {
    private final JdbcClient jdbc;

    public MeasurementRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public boolean storeIdentity(RawMeasurement measurement) {
        return jdbc.sql("""
                        INSERT INTO measurement
                            (measurement_id, sensor_id, captured_at, raw_value, calibrated_value)
                        VALUES (:id, :sensor, :captured, :raw, :calibrated)
                        ON CONFLICT (measurement_id) DO NOTHING
                        """)
                .param("id", measurement.measurementId())
                .param("sensor", measurement.sensorId())
                .param("captured", measurement.capturedAt())
                .param("raw", measurement.rawValue())
                .param("calibrated", measurement.rawValue())
                .update() == 1;
    }

    public Optional<StoredMeasurement> find(String id) {
        return jdbc.sql("""
                        SELECT measurement_id, sensor_id, captured_at, raw_value, calibrated_value
                        FROM measurement WHERE measurement_id = :id
                        """)
                .param("id", id)
                .query((rs, row) -> new StoredMeasurement(
                        rs.getString("measurement_id"),
                        rs.getString("sensor_id"),
                        rs.getObject("captured_at", OffsetDateTime.class),
                        rs.getBigDecimal("raw_value"),
                        rs.getBigDecimal("calibrated_value")))
                .optional();
    }

    public record StoredMeasurement(
            String measurementId,
            String sensorId,
            OffsetDateTime capturedAt,
            BigDecimal rawValue,
            BigDecimal calibratedValue) {
    }
}
