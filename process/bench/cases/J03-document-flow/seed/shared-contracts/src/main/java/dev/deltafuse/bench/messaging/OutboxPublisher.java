package dev.deltafuse.bench.messaging;

import dev.deltafuse.bench.contracts.AggregateType;
import dev.deltafuse.bench.contracts.BaselineEvents;
import dev.deltafuse.bench.contracts.CanonicalJson;
import dev.deltafuse.bench.contracts.EventEnvelope;
import dev.deltafuse.bench.contracts.JsonObj;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Duration;
import javax.sql.DataSource;
import org.apache.kafka.clients.producer.Producer;
import org.apache.kafka.clients.producer.ProducerRecord;

/** Bounded transactional outbox publisher. A crash may republish, never lose, an event. */
public final class OutboxPublisher {
    private final DataSource dataSource;
    private final Producer<String, String> producer;
    private final String topic;
    private final int batchSize;
    private final Duration sendTimeout;
    private final DeliveryHook hook;

    public OutboxPublisher(DataSource dataSource, Producer<String, String> producer, String topic,
            int batchSize, Duration sendTimeout) {
        this(dataSource, producer, topic, batchSize, sendTimeout, DeliveryHook.NONE);
    }

    public OutboxPublisher(DataSource dataSource, Producer<String, String> producer, String topic,
            int batchSize, Duration sendTimeout, DeliveryHook hook) {
        if (batchSize < 1 || batchSize > 1000) throw new IllegalArgumentException("invalid batch size");
        this.dataSource = dataSource;
        this.producer = producer;
        this.topic = topic;
        this.batchSize = batchSize;
        this.sendTimeout = sendTimeout;
        this.hook = hook;
    }

    public int publishBatch() {
        try (Connection connection = dataSource.getConnection()) {
            connection.setAutoCommit(false);
            try {
                seedDeliveryRows(connection);
                int count = 0;
                try (PreparedStatement statement = connection.prepareStatement(
                        "SELECT o.event_id,o.aggregate_type,o.aggregate_id,o.domain_sequence,o.schema_name,"+
                        "o.schema_version,o.payload::text,o.created_at FROM outbox_event o JOIN outbox_delivery d " +
                        "ON d.event_id=o.event_id WHERE d.sent_at IS NULL ORDER BY o.created_at,o.event_id " +
                        "LIMIT ? FOR UPDATE OF d SKIP LOCKED")) {
                    statement.setInt(1, batchSize);
                    try (ResultSet rows = statement.executeQuery()) {
                        while (rows.next()) {
                            String eventId = rows.getString(1);
                            EventEnvelope envelope = new EventEnvelope(rows.getString(5), rows.getInt(6), eventId,
                                    producerName(rows.getString(2)), AggregateType.parse(rows.getString(2)),
                                    rows.getString(3), rows.getLong(4), eventId, null,
                                    rows.getTimestamp(8).toInstant().toString());
                            JsonObj payload = (JsonObj) CanonicalJson.parse(rows.getString(7));
                            String wire = BaselineEvents.encode(envelope, payload);
                            producer.send(new ProducerRecord<>(topic, envelope.aggregateId(), wire))
                                    .get(sendTimeout.toMillis(), java.util.concurrent.TimeUnit.MILLISECONDS);
                            producer.flush();
                            hook.reached(DeliveryBarrier.AFTER_PUBLISH_BEFORE_SENT);
                            markSent(connection, eventId);
                            count++;
                        }
                    }
                }
                connection.commit();
                return count;
            } catch (Exception failure) {
                connection.rollback();
                if (failure instanceof RuntimeException runtime) throw runtime;
                throw new IllegalStateException("outbox publish failed", failure);
            }
        } catch (SQLException failure) {
            throw new IllegalStateException("outbox database unavailable", failure);
        }
    }

    private static String producerName(String aggregateType) {
        return "DOCUMENT".equals(aggregateType) ? "document-service" : "workflow-service";
    }

    private static void seedDeliveryRows(Connection connection) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                "INSERT INTO outbox_delivery(event_id) SELECT event_id FROM outbox_event ON CONFLICT DO NOTHING")) {
            statement.executeUpdate();
        }
    }

    private static void markSent(Connection connection, String eventId) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                "UPDATE outbox_delivery SET attempts=attempts+1,last_attempt_at=now(),sent_at=now() WHERE event_id=?")) {
            statement.setString(1, eventId);
            statement.executeUpdate();
        }
    }
}
