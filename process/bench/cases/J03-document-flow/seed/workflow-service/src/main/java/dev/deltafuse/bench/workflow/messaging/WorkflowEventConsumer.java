package dev.deltafuse.bench.workflow.messaging;

import dev.deltafuse.bench.contracts.BaselineEvents;
import dev.deltafuse.bench.contracts.CanonicalJson;
import dev.deltafuse.bench.contracts.ContractViolation;
import dev.deltafuse.bench.contracts.JsonObj;
import dev.deltafuse.bench.contracts.JsonStr;
import dev.deltafuse.bench.contracts.VersionSubmitted;
import dev.deltafuse.bench.messaging.DeadLetterReason;
import dev.deltafuse.bench.messaging.DeliveryBarrier;
import dev.deltafuse.bench.messaging.DeliveryHook;
import dev.deltafuse.bench.workflow.WorkflowCommandService;
import dev.deltafuse.bench.workflow.WorkflowFailure;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.HexFormat;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import org.apache.kafka.clients.producer.Producer;
import org.apache.kafka.clients.producer.ProducerRecord;

/** At-least-once adapter: database work commits before the caller acknowledges Kafka. */
public final class WorkflowEventConsumer {
    private final WorkflowCommandService commands;
    private final Producer<String, String> producer;
    private final String deadLetterTopic;
    private final Duration sendTimeout;
    private final DeliveryHook hook;

    public WorkflowEventConsumer(WorkflowCommandService commands, Producer<String, String> producer,
            String deadLetterTopic, Duration sendTimeout) {
        this(commands, producer, deadLetterTopic, sendTimeout, DeliveryHook.NONE);
    }

    public WorkflowEventConsumer(WorkflowCommandService commands, Producer<String, String> producer,
            String deadLetterTopic, Duration sendTimeout, DeliveryHook hook) {
        this.commands = commands;
        this.producer = producer;
        this.deadLetterTopic = deadLetterTopic;
        this.sendTimeout = sendTimeout;
        this.hook = hook;
    }

    public void consume(String rawEvent, Acknowledgement acknowledgement) {
        BaselineEvents.Decoded decoded;
        try {
            decoded = BaselineEvents.decode(rawEvent);
        } catch (ContractViolation | IllegalArgumentException failure) {
            reject(rawEvent, classify(failure), failure.getMessage(), acknowledgement);
            return;
        }
        if (!(decoded.payload() instanceof VersionSubmitted submission)
                || !"j03.document.version-submitted".equals(decoded.envelope().schemaName())) {
            reject(rawEvent, DeadLetterReason.UNSUPPORTED_EVENT,
                    "workflow accepts only j03.document.version-submitted", acknowledgement);
            return;
        }
        try {
            String routeId = derived("route", decoded.envelope().eventId());
            String outputEventId = derived("event", decoded.envelope().eventId());
            commands.createRoute(decoded.envelope(), submission, routeId, "baseline-approver", outputEventId);
        } catch (WorkflowFailure failure) {
            reject(rawEvent, DeadLetterReason.INVALID_CONTRACT, failure.getMessage(), acknowledgement);
            return;
        }
        hook.reached(DeliveryBarrier.AFTER_COMMIT_BEFORE_ACK);
        acknowledgement.acknowledge();
    }

    private void reject(String raw, DeadLetterReason reason, String detail, Acknowledgement acknowledgement) {
        String hash = sha256(raw);
        String payload = CanonicalJson.write(JsonObj.of(Map.of(
                "detail", new JsonStr(safeDetail(detail)),
                "raw_sha256", new JsonStr(hash),
                "reason", new JsonStr(reason.name()))));
        try {
            producer.send(new ProducerRecord<>(deadLetterTopic, hash, payload))
                    .get(sendTimeout.toMillis(), TimeUnit.MILLISECONDS);
            producer.flush();
        } catch (Exception failure) {
            throw new IllegalStateException("dead-letter publish failed", failure);
        }
        acknowledgement.acknowledge();
    }

    private static DeadLetterReason classify(RuntimeException failure) {
        return failure.getMessage() != null && failure.getMessage().startsWith("malformed event JSON")
                ? DeadLetterReason.MALFORMED_JSON : DeadLetterReason.INVALID_CONTRACT;
    }

    private static String safeDetail(String value) {
        String text = value == null ? "invalid event" : value.replaceAll("[\\p{Cntrl}]", " ");
        return text.length() <= 512 ? text : text.substring(0, 512);
    }

    private static String derived(String namespace, String eventId) {
        return UUID.nameUUIDFromBytes((namespace + ":" + eventId).getBytes(StandardCharsets.UTF_8)).toString();
    }

    private static String sha256(String value) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    @FunctionalInterface
    public interface Acknowledgement { void acknowledge(); }
}
