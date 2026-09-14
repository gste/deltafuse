package dev.deltafuse.bench.document;
import com.zaxxer.hikari.*;
import dev.deltafuse.bench.document.query.*;
import java.util.*;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.*;
import org.testcontainers.containers.PostgreSQLContainer;
import static org.junit.jupiter.api.Assertions.*;

@Tag("messaging-integration")
class QueryFlowTest {
 @Test void canonicalAggregationIsReadOnlyOrderedAndReportsUnavailable()throws Exception{
  try(var pg=new PostgreSQLContainer<>("postgres:17.6")){pg.start();try(var data=data(pg)){
   Flyway.configure().dataSource(data).locations("classpath:db/migration").load().migrate();var commands=new DocumentCommandService(data);commands.createDocument("op-1","event-1","doc-1","Title");commands.createVersion("op-2","event-2","doc-1","ver-1","body");commands.submitVersion("op-3","event-3","doc-1","ver-1");
   var w=new WorkflowProjectionClient.WorkflowProjection(true,"route-1","PENDING",1,List.of(new WorkflowProjectionClient.OpenSlot("approver","actor-1")));
   var entries=List.of(new AuditProjectionClient.AuditEntry(12,"event-3","submitted"),new AuditProjectionClient.AuditEntry(10,"event-1","created"));
   var service=new FlowQueryService(data,id->w,id->new AuditProjectionClient.AuditProjection(true,3,entries));long before=scalar(data,"SELECT count(*) FROM document")+scalar(data,"SELECT count(*) FROM document_version")+scalar(data,"SELECT count(*) FROM outbox_event");String json=service.flow("doc-1");String again=service.flow("doc-1");assertEquals(json,again);assertTrue(json.indexOf("event-1")<json.indexOf("event-3"),json);assertTrue(json.contains("\"caught_up\":true"),json);assertTrue(json.contains("\"immutable\":true"),json);assertEquals(before,scalar(data,"SELECT count(*) FROM document")+scalar(data,"SELECT count(*) FROM document_version")+scalar(data,"SELECT count(*) FROM outbox_event"));
   var unavailable=new FlowQueryService(data,id->{throw new IllegalStateException("down");},id->{throw new IllegalStateException("down");}).flow("doc-1");assertTrue(unavailable.contains("\"caught_up\":false"),unavailable);assertTrue(unavailable.contains("\"workflow\":null"),unavailable);
   var missing=assertThrows(DocumentFailure.class,()->service.flow("missing"));assertEquals(dev.deltafuse.bench.contracts.ErrorCode.DOCUMENT_NOT_FOUND,missing.code());
  }}
 }
 private static HikariDataSource data(PostgreSQLContainer<?>p){var c=new HikariConfig();c.setJdbcUrl(p.getJdbcUrl());c.setUsername(p.getUsername());c.setPassword(p.getPassword());return new HikariDataSource(c);}
 private static long scalar(HikariDataSource d,String q)throws Exception{try(var c=d.getConnection();var s=c.prepareStatement(q);var r=s.executeQuery()){r.next();return r.getLong(1);}}
}
