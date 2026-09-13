package dev.deltafuse.bench.gateway;

import dev.deltafuse.bench.contracts.RawMeasurement;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
public class MeasurementPublisher {
    static final String TOPIC = "telemetry.raw.v1";

    private final KafkaTemplate<String, RawMeasurement> kafka;

    public MeasurementPublisher(KafkaTemplate<String, RawMeasurement> kafka) {
        this.kafka = kafka;
    }

    public void publish(RawMeasurement measurement) {
        kafka.send(TOPIC, measurement.sensorId(), measurement);
    }
}
