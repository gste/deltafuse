package dev.deltafuse.bench.gateway;

import dev.deltafuse.bench.contracts.RawMeasurement;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/measurements")
public class MeasurementController {
    private final MeasurementPublisher publisher;

    public MeasurementController(MeasurementPublisher publisher) {
        this.publisher = publisher;
    }

    @PostMapping
    public ResponseEntity<Void> accept(@RequestBody RawMeasurement measurement) {
        if (measurement.measurementId() == null || measurement.measurementId().isBlank()
                || measurement.sensorId() == null || measurement.sensorId().isBlank()
                || measurement.capturedAt() == null || measurement.rawValue() == null) {
            return ResponseEntity.badRequest().build();
        }
        publisher.publish(measurement);
        return ResponseEntity.accepted().build();
    }
}
