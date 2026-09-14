package dev.deltafuse.bench.document;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import dev.deltafuse.bench.messaging.DeliveryBarrier;
import dev.deltafuse.bench.messaging.OutboxPublisher;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.concurrent.atomic.AtomicBoolean;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.kafka.KafkaContainer;
import org.testcontainers.utility.DockerImageName;
import static org.junit.jupiter.api.Assertions.*;

@Tag("messaging-integration")
class DeliveryOutboxIntegrationTest {
    @Test void publishBeforeSentCrashRepublishesAfterPublisherRestart() throws Exception {
        try (PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:17.6");
             KafkaContainer kafka = new KafkaContainer(DockerImageName.parse("apache/kafka-native:3.9.1"))) {
            postgres.start(); kafka.start();
            try (HikariDataSource data = dataSource(postgres);
                 KafkaProducer<String,String> producer = producer(kafka.getBootstrapServers())) {
                Flyway.configure().dataSource(data).locations("classpath:db/migration").load().migrate();
                insertEvent(data);
                AtomicBoolean crash = new AtomicBoolean(true);
                OutboxPublisher first = new OutboxPublisher(data, producer, "document-events", 1,
                        Duration.ofSeconds(10), barrier -> {
                            if (barrier == DeliveryBarrier.AFTER_PUBLISH_BEFORE_SENT && crash.getAndSet(false))
                                throw new MeasuredCrash();
                        });
                assertThrows(MeasuredCrash.class, first::publishBatch);
                assertEquals(0, scalar(data, "SELECT count(*) FROM outbox_delivery WHERE sent_at IS NOT NULL"));
                OutboxPublisher restarted = new OutboxPublisher(data, producer, "document-events", 1, Duration.ofSeconds(10));
                assertEquals(1, restarted.publishBatch());
                assertEquals(0, restarted.publishBatch());
                assertEquals(1, scalar(data, "SELECT count(*) FROM outbox_delivery WHERE sent_at IS NOT NULL"));
                assertEquals(2, receive(kafka.getBootstrapServers(), "document-events", 2).size());
            }
        }
    }
    private static void insertEvent(HikariDataSource data) throws Exception {try(var c=data.getConnection();var s=c.prepareStatement("INSERT INTO outbox_event (event_id,aggregate_type,aggregate_id,domain_sequence,schema_name,schema_version,payload) VALUES ('evt-1','DOCUMENT','doc-1',1,'j03.document.created',1,'{\"document_id\":\"doc-1\",\"title\":\"Title\"}'::jsonb)")){s.executeUpdate();}}
    private static long scalar(HikariDataSource data,String sql)throws Exception{try(var c=data.getConnection();var s=c.prepareStatement(sql);var r=s.executeQuery()){r.next();return r.getLong(1);}}
    private static HikariDataSource dataSource(PostgreSQLContainer<?> p){var c=new HikariConfig();c.setJdbcUrl(p.getJdbcUrl());c.setUsername(p.getUsername());c.setPassword(p.getPassword());return new HikariDataSource(c);}
    private static KafkaProducer<String,String> producer(String bootstrap){return new KafkaProducer<>(Map.of(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG,bootstrap,ProducerConfig.ACKS_CONFIG,"all",ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG,"true"),new StringSerializer(),new StringSerializer());}
    private static List<String> receive(String bootstrap,String topic,int wanted){Properties p=new Properties();p.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,bootstrap);p.put(ConsumerConfig.GROUP_ID_CONFIG,"observe-"+System.nanoTime());p.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG,"earliest");p.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG,"false");try(var c=new KafkaConsumer<String,String>(p,new StringDeserializer(),new StringDeserializer())){c.subscribe(List.of(topic));var values=new java.util.ArrayList<String>();long end=System.nanoTime()+Duration.ofSeconds(15).toNanos();while(values.size()<wanted&&System.nanoTime()<end)c.poll(Duration.ofMillis(250)).forEach(r->values.add(r.value()));return values;}}
    private static final class MeasuredCrash extends RuntimeException {}
}
