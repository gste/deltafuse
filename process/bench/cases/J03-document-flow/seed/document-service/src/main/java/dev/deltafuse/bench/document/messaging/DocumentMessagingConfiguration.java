package dev.deltafuse.bench.document.messaging;

import dev.deltafuse.bench.messaging.OutboxPublisher;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;
import javax.sql.DataSource;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.Producer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;

@Configuration
@EnableScheduling
@ConditionalOnProperty(name="j03.messaging.enabled", havingValue="true")
public class DocumentMessagingConfiguration {
    @Bean(destroyMethod="close") Producer<String,String> documentKafkaProducer(
            @Value("${spring.kafka.bootstrap-servers}") String bootstrap) {
        Map<String,Object> config=new HashMap<>();
        config.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG,bootstrap);
        config.put(ProducerConfig.ACKS_CONFIG,"all");
        config.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG,true);
        return new KafkaProducer<>(config,new StringSerializer(),new StringSerializer());
    }
    @Bean OutboxPublisher documentOutboxPublisher(DataSource data,Producer<String,String> documentKafkaProducer,
            @Value("${j03.messaging.document-topic:j03.document-events}") String topic) {
        return new OutboxPublisher(data,documentKafkaProducer,topic,100,Duration.ofSeconds(15));
    }
    @Bean DocumentOutboxPump documentOutboxPump(OutboxPublisher publisher){return new DocumentOutboxPump(publisher);}

    public static final class DocumentOutboxPump {
        private final OutboxPublisher publisher;
        DocumentOutboxPump(OutboxPublisher publisher){this.publisher=publisher;}
        @Scheduled(fixedDelayString="${j03.messaging.poll-delay-ms:250}") public void poll(){publisher.publishBatch();}
    }
}
