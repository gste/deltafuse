package dev.deltafuse.bench.workflow.messaging;

import dev.deltafuse.bench.messaging.OutboxPublisher;
import dev.deltafuse.bench.workflow.WorkflowCommandService;
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
import org.springframework.kafka.annotation.EnableKafka;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.kafka.listener.ContainerProperties;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;

@Configuration
@EnableKafka
@EnableScheduling
@ConditionalOnProperty(name="j03.messaging.enabled",havingValue="true")
public class WorkflowMessagingConfiguration {
    @Bean(destroyMethod="close") Producer<String,String> workflowKafkaProducer(@Value("${spring.kafka.bootstrap-servers}")String bootstrap){Map<String,Object> c=new HashMap<>();c.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG,bootstrap);c.put(ProducerConfig.ACKS_CONFIG,"all");c.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG,true);return new KafkaProducer<>(c,new StringSerializer(),new StringSerializer());}
    @Bean OutboxPublisher workflowOutboxPublisher(DataSource data,Producer<String,String> workflowKafkaProducer,@Value("${j03.messaging.workflow-topic:j03.workflow-events}")String topic){return new OutboxPublisher(data,workflowKafkaProducer,topic,100,Duration.ofSeconds(15));}
    @Bean WorkflowEventConsumer workflowEventConsumer(WorkflowCommandService commands,Producer<String,String> workflowKafkaProducer,@Value("${j03.messaging.dlq-topic:j03.workflow-dlq}")String dlq){return new WorkflowEventConsumer(commands,workflowKafkaProducer,dlq,Duration.ofSeconds(15));}
    @Bean(name="kafkaListenerContainerFactory") ConcurrentKafkaListenerContainerFactory<String,String> kafkaListenerContainerFactory(@Value("${spring.kafka.bootstrap-servers}")String bootstrap){Map<String,Object> c=new HashMap<>();c.put(org.apache.kafka.clients.consumer.ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,bootstrap);c.put(org.apache.kafka.clients.consumer.ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG,false);c.put(org.apache.kafka.clients.consumer.ConsumerConfig.AUTO_OFFSET_RESET_CONFIG,"earliest");c.put(org.apache.kafka.clients.consumer.ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG,org.apache.kafka.common.serialization.StringDeserializer.class);c.put(org.apache.kafka.clients.consumer.ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG,org.apache.kafka.common.serialization.StringDeserializer.class);var factory=new ConcurrentKafkaListenerContainerFactory<String,String>();factory.setConsumerFactory(new DefaultKafkaConsumerFactory<>(c));factory.getContainerProperties().setAckMode(ContainerProperties.AckMode.MANUAL_IMMEDIATE);return factory;}
    @Bean WorkflowListener workflowListener(WorkflowEventConsumer consumer){return new WorkflowListener(consumer);}
    @Bean WorkflowOutboxPump workflowOutboxPump(OutboxPublisher publisher){return new WorkflowOutboxPump(publisher);}

    public static final class WorkflowListener {
        private final WorkflowEventConsumer consumer;
        WorkflowListener(WorkflowEventConsumer consumer){this.consumer=consumer;}
        @KafkaListener(topics="${j03.messaging.document-topic:j03.document-events}",groupId="${j03.messaging.workflow-group:j03-workflow}",containerFactory="kafkaListenerContainerFactory")
        public void receive(String value,Acknowledgment ack){consumer.consume(value,ack::acknowledge);}
    }
    public static final class WorkflowOutboxPump {
        private final OutboxPublisher publisher;
        WorkflowOutboxPump(OutboxPublisher publisher){this.publisher=publisher;}
        @Scheduled(fixedDelayString="${j03.messaging.poll-delay-ms:250}") public void poll(){publisher.publishBatch();}
    }
}
