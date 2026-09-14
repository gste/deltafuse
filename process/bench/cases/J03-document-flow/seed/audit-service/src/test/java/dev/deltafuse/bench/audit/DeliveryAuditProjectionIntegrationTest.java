package dev.deltafuse.bench.audit;
import com.zaxxer.hikari.*;
import dev.deltafuse.bench.audit.messaging.AuditProjectionService;
import dev.deltafuse.bench.audit.query.AuditQueryService;
import dev.deltafuse.bench.contracts.*;
import java.time.Duration;
import java.util.*;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.serialization.*;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.*;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.kafka.KafkaContainer;
import org.testcontainers.utility.DockerImageName;
import static org.junit.jupiter.api.Assertions.*;

@Tag("messaging-integration")
class DeliveryAuditProjectionIntegrationTest {
 @Test void reorderedDeliveryAndFullTopicReplayProduceOneStableTrail()throws Exception{
  try(var pg=new PostgreSQLContainer<>("postgres:17.6");var kafka=new KafkaContainer(DockerImageName.parse("apache/kafka-native:3.9.1"))){pg.start();kafka.start();try(var data=data(pg);var producer=producer(kafka.getBootstrapServers())){
   Flyway.configure().dataSource(data).locations("classpath:db/migration").load().migrate();
   List<String> events=List.of(route(),version(),document());for(String e:events)producer.send(new ProducerRecord<>("audit-input","doc-1",e)).get();producer.flush();
   var projection=new AuditProjectionService(data);consumeAll(kafka.getBootstrapServers(),"first",projection,3);
   assertEquals(3,scalar(data,"SELECT count(*) FROM audit_event"));String first=new AuditQueryService(data).trail("doc-1");
   consumeAll(kafka.getBootstrapServers(),"replay",projection,3);
   assertEquals(3,scalar(data,"SELECT count(*) FROM audit_event"));assertEquals(first,new AuditQueryService(data).trail("doc-1"));
   assertTrue(first.indexOf("doc-created")<first.indexOf("route-created"),first);assertTrue(first.indexOf("route-created")<first.indexOf("ver-created"),first);
   assertEquals(2,scalar(data,"SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('audit_event','inbox_event')"));
  }}
 }
 private static void consumeAll(String bootstrap,String group,AuditProjectionService service,int count){Properties p=new Properties();p.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,bootstrap);p.put(ConsumerConfig.GROUP_ID_CONFIG,group);p.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG,"earliest");p.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG,"false");try(var c=new KafkaConsumer<String,String>(p,new StringDeserializer(),new StringDeserializer())){c.subscribe(List.of("audit-input"));int seen=0;long end=System.nanoTime()+Duration.ofSeconds(15).toNanos();while(seen<count&&System.nanoTime()<end){for(var r:c.poll(Duration.ofMillis(250))){service.consume(r.value());seen++;}}assertEquals(count,seen,"bounded Kafka replay");}}
 private static String document(){return encode(new EventEnvelope("j03.document.created",1,"doc-created","document-service",AggregateType.DOCUMENT,"doc-1",1,"op",null,null),new DocumentCreated("doc-1","Title"));}
 private static String version(){return encode(new EventEnvelope("j03.document.version-created",1,"ver-created","document-service",AggregateType.DOCUMENT,"doc-1",2,"op",null,null),new VersionCreated("doc-1","ver-1","body"));}
 private static String route(){return encode(new EventEnvelope("j03.workflow.route-created",1,"route-created","workflow-service",AggregateType.ROUTE,"route-1",1,"op",null,null),new RouteCreated("doc-1","ver-1","route-1","actor-1"));}
 private static String encode(EventEnvelope e,Payload p){return BaselineEvents.encode(e,p.toJson());}
 private static HikariDataSource data(PostgreSQLContainer<?>p){var c=new HikariConfig();c.setJdbcUrl(p.getJdbcUrl());c.setUsername(p.getUsername());c.setPassword(p.getPassword());return new HikariDataSource(c);}
 private static KafkaProducer<String,String> producer(String b){return new KafkaProducer<>(Map.of(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG,b,ProducerConfig.ACKS_CONFIG,"all"),new StringSerializer(),new StringSerializer());}
 private static long scalar(HikariDataSource d,String q)throws Exception{try(var c=d.getConnection();var s=c.prepareStatement(q);var r=s.executeQuery()){r.next();return r.getLong(1);}}
}
