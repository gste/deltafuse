package dev.deltafuse.bench.workflow;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import dev.deltafuse.bench.contracts.*;
import dev.deltafuse.bench.messaging.DeliveryBarrier;
import dev.deltafuse.bench.workflow.messaging.WorkflowEventConsumer;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.*;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.kafka.KafkaContainer;
import org.testcontainers.utility.DockerImageName;
import static org.junit.jupiter.api.Assertions.*;

@Tag("messaging-integration")
class DeliveryConsumerIntegrationTest {
    @Test void commitBeforeAckRedeliveryHasOneEffectAndMalformedGoesToDlq() throws Exception {
        try (PostgreSQLContainer<?> postgres=new PostgreSQLContainer<>("postgres:17.6"); KafkaContainer kafka=new KafkaContainer(DockerImageName.parse("apache/kafka-native:3.9.1"))) {
            postgres.start(); kafka.start();
            try(HikariDataSource data=dataSource(postgres);KafkaProducer<String,String> producer=producer(kafka.getBootstrapServers())){
                Flyway.configure().dataSource(data).locations("classpath:db/migration").load().migrate();
                producer.send(new ProducerRecord<>("document-events","doc-1",event("input-1"))).get(); producer.flush();
                AtomicBoolean crash=new AtomicBoolean(true);
                WorkflowEventConsumer first=new WorkflowEventConsumer(new WorkflowCommandService(data),producer,"workflow-dlq",Duration.ofSeconds(10),barrier->{if(barrier==DeliveryBarrier.AFTER_COMMIT_BEFORE_ACK&&crash.getAndSet(false))throw new MeasuredCrash();});
                try(KafkaConsumer<String,String> consumer=consumer(kafka.getBootstrapServers(),"workflow-group")){
                    ConsumerRecord<String,String> record=next(consumer,"document-events");
                    assertThrows(MeasuredCrash.class,()->first.consume(record.value(),()->commit(consumer,record)));
                }
                try(KafkaConsumer<String,String> restarted=consumer(kafka.getBootstrapServers(),"workflow-group")){
                    ConsumerRecord<String,String> duplicate=next(restarted,"document-events");
                    new WorkflowEventConsumer(new WorkflowCommandService(data),producer,"workflow-dlq",Duration.ofSeconds(10)).consume(duplicate.value(),()->commit(restarted,duplicate));
                }
                assertEquals(1,scalar(data,"SELECT count(*) FROM inbox_event"));
                assertEquals(1,scalar(data,"SELECT count(*) FROM route"));
                assertEquals(1,scalar(data,"SELECT count(*) FROM outbox_event"));
                long before=scalar(data,"SELECT count(*) FROM route");
                producer.send(new ProducerRecord<>("bad-events","x","{not-json")).get();producer.flush();
                try(KafkaConsumer<String,String> bad=consumer(kafka.getBootstrapServers(),"bad-group")){
                    ConsumerRecord<String,String> malformed=next(bad,"bad-events");
                    new WorkflowEventConsumer(new WorkflowCommandService(data),producer,"workflow-dlq",Duration.ofSeconds(10)).consume(malformed.value(),()->commit(bad,malformed));
                }
                assertEquals(before,scalar(data,"SELECT count(*) FROM route"));
                String dlq=observe(kafka.getBootstrapServers(),"workflow-dlq");
                assertTrue(dlq.contains("\"reason\":\"MALFORMED_JSON\""),dlq);
            }
        }
    }
    private static String event(String id){var e=new EventEnvelope("j03.document.version-submitted",1,id,"document-service",AggregateType.DOCUMENT,"doc-1",2,id,null,null);return BaselineEvents.encode(e,new VersionSubmitted("doc-1","ver-1").toJson());}
    private static void commit(KafkaConsumer<String,String> c,ConsumerRecord<String,String> r){c.commitSync(Map.of(new TopicPartition(r.topic(),r.partition()),new OffsetAndMetadata(r.offset()+1)));}
    private static ConsumerRecord<String,String> next(KafkaConsumer<String,String> c,String topic){c.subscribe(List.of(topic));long end=System.nanoTime()+Duration.ofSeconds(15).toNanos();while(System.nanoTime()<end){var records=c.poll(Duration.ofMillis(250));if(!records.isEmpty())return records.iterator().next();}throw new AssertionError("bounded poll timed out for "+topic);}
    private static String observe(String bootstrap,String topic){try(var c=consumer(bootstrap,"observe-"+System.nanoTime())){return next(c,topic).value();}}
    private static KafkaConsumer<String,String> consumer(String bootstrap,String group){Properties p=new Properties();p.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,bootstrap);p.put(ConsumerConfig.GROUP_ID_CONFIG,group);p.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG,"earliest");p.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG,"false");return new KafkaConsumer<>(p,new StringDeserializer(),new StringDeserializer());}
    private static KafkaProducer<String,String> producer(String bootstrap){return new KafkaProducer<>(Map.of(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG,bootstrap,ProducerConfig.ACKS_CONFIG,"all",ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG,"true"),new StringSerializer(),new StringSerializer());}
    private static HikariDataSource dataSource(PostgreSQLContainer<?> p){var c=new HikariConfig();c.setJdbcUrl(p.getJdbcUrl());c.setUsername(p.getUsername());c.setPassword(p.getPassword());return new HikariDataSource(c);}
    private static long scalar(HikariDataSource data,String sql)throws Exception{try(var c=data.getConnection();var s=c.prepareStatement(sql);var r=s.executeQuery()){r.next();return r.getLong(1);}}
    private static final class MeasuredCrash extends RuntimeException {}
}
