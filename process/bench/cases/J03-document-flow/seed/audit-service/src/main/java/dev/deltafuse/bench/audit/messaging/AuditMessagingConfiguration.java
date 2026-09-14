package dev.deltafuse.bench.audit.messaging;

import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.*;
import org.springframework.kafka.annotation.*;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.kafka.listener.ContainerProperties;
import org.springframework.kafka.support.Acknowledgment;

@Configuration
@EnableKafka
@ConditionalOnProperty(name="j03.messaging.enabled",havingValue="true")
public class AuditMessagingConfiguration {
    @Bean(name="auditKafkaListenerContainerFactory") ConcurrentKafkaListenerContainerFactory<String,String> auditFactory(@Value("${spring.kafka.bootstrap-servers}")String bootstrap){Map<String,Object> c=new HashMap<>();c.put(org.apache.kafka.clients.consumer.ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,bootstrap);c.put(org.apache.kafka.clients.consumer.ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG,false);c.put(org.apache.kafka.clients.consumer.ConsumerConfig.AUTO_OFFSET_RESET_CONFIG,"earliest");c.put(org.apache.kafka.clients.consumer.ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG,org.apache.kafka.common.serialization.StringDeserializer.class);c.put(org.apache.kafka.clients.consumer.ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG,org.apache.kafka.common.serialization.StringDeserializer.class);var f=new ConcurrentKafkaListenerContainerFactory<String,String>();f.setConsumerFactory(new DefaultKafkaConsumerFactory<>(c));f.getContainerProperties().setAckMode(ContainerProperties.AckMode.MANUAL_IMMEDIATE);return f;}
    @Bean AuditListener auditListener(AuditProjectionService service){return new AuditListener(service);}
    public static final class AuditListener {
        private final AuditProjectionService service;
        AuditListener(AuditProjectionService service){this.service=service;}
        @KafkaListener(topics={"${j03.messaging.document-topic:j03.document-events}","${j03.messaging.workflow-topic:j03.workflow-events}"},groupId="${j03.messaging.audit-group:j03-audit}",containerFactory="auditKafkaListenerContainerFactory")
        public void receive(String value,Acknowledgment ack){service.consume(value);ack.acknowledge();}
    }
}
