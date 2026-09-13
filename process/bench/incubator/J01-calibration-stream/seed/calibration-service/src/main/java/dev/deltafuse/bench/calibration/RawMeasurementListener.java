package dev.deltafuse.bench.calibration;

import dev.deltafuse.bench.contracts.RawMeasurement;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class RawMeasurementListener {
    private final MeasurementRepository repository;

    public RawMeasurementListener(MeasurementRepository repository) {
        this.repository = repository;
    }

    @KafkaListener(topics = "telemetry.raw.v1", groupId = "calibration-service")
    @Transactional
    public void accept(RawMeasurement measurement) {
        repository.storeIdentity(measurement);
    }
}
