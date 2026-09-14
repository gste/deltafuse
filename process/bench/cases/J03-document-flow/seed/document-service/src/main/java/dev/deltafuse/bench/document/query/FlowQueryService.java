package dev.deltafuse.bench.document.query;

import dev.deltafuse.bench.contracts.*;
import dev.deltafuse.bench.document.DocumentFailure;
import java.sql.*;
import java.util.*;
import javax.sql.DataSource;

/** Read-only canonical aggregation; it never replays topics or writes projections. */
public final class FlowQueryService {
    private final DataSource dataSource; private final WorkflowProjectionClient workflow; private final AuditProjectionClient audit;
    public FlowQueryService(DataSource dataSource,WorkflowProjectionClient workflow,AuditProjectionClient audit){this.dataSource=dataSource;this.workflow=workflow;this.audit=audit;}
    public String flow(String documentId){
        Local local=local(documentId); WorkflowProjectionClient.WorkflowProjection w=safeWorkflow(documentId); AuditProjectionClient.AuditProjection a=safeAudit(documentId);
        List<JsonValue> slots=new ArrayList<>();w.openSlots().stream().sorted(Comparator.comparingInt(s->roleOrder(s.role()))).forEach(s->slots.add(JsonObj.of(Map.of("assigned_actor_id",new JsonStr(s.assignedActorId()),"role",new JsonStr(s.role())))));
        List<JsonValue> auditEntries=new ArrayList<>();a.entries().stream().sorted(Comparator.comparingLong(AuditProjectionClient.AuditEntry::sequence).thenComparing(AuditProjectionClient.AuditEntry::eventId)).forEach(e->auditEntries.add(JsonObj.of(Map.of("event_id",new JsonStr(e.eventId()),"kind",new JsonStr(e.kind()),"sequence",new JsonNum(e.sequence())))));
        long required=local.versionId()==null?0:1; boolean caught=w.available()&&a.available()&&(required==0||(w.routeId()!=null&&w.sequence()>=1&&a.sequence()>=local.documentSequence()));
        JsonValue active=local.versionId()==null?JsonNull.INSTANCE:JsonObj.of(Map.of("immutable",new JsonBool(local.immutable()),"version_id",new JsonStr(local.versionId())));
        JsonValue route=w.routeId()==null?JsonNull.INSTANCE:JsonObj.of(Map.of("route_id",new JsonStr(w.routeId()),"state",new JsonStr(w.state())));
        return CanonicalJson.write(JsonObj.of(Map.of("active_version",active,"audit_sequence",new JsonArr(auditEntries),"document",JsonObj.of(Map.of("document_id",new JsonStr(documentId))),"open_slots",new JsonArr(slots),"watermark",JsonObj.of(Map.of("audit_sequence",new JsonNum(a.sequence()),"caught_up",new JsonBool(caught),"document_sequence",new JsonNum(local.documentSequence()),"required_sequence",new JsonNum(required),"workflow_sequence",new JsonNum(w.sequence()))),"workflow",route)));
    }
    private Local local(String id){try(Connection c=dataSource.getConnection()){c.setReadOnly(true);try(var d=c.prepareStatement("SELECT document_id FROM document WHERE document_id=?")){d.setString(1,id);try(var r=d.executeQuery()){if(!r.next())throw new DocumentFailure(ErrorCode.DOCUMENT_NOT_FOUND,id,"document not found");}}String version=null;boolean immutable=false;try(var s=c.prepareStatement("SELECT version_id,state FROM document_version WHERE document_id=? ORDER BY created_at DESC,version_id DESC LIMIT 1")){s.setString(1,id);try(var r=s.executeQuery()){if(r.next()){version=r.getString(1);immutable=!"DRAFT".equals(r.getString(2));}}}long sequence=0;try(var s=c.prepareStatement("SELECT COALESCE(MAX(domain_sequence),0) FROM outbox_event WHERE aggregate_type='DOCUMENT' AND aggregate_id=?")){s.setString(1,id);try(var r=s.executeQuery()){r.next();sequence=r.getLong(1);}}return new Local(version,immutable,sequence);}catch(SQLException e){throw new IllegalStateException("document query unavailable",e);}}
    private WorkflowProjectionClient.WorkflowProjection safeWorkflow(String id){try{return Objects.requireNonNull(workflow.read(id));}catch(RuntimeException e){return new WorkflowProjectionClient.WorkflowProjection(false,null,null,0,List.of());}}
    private AuditProjectionClient.AuditProjection safeAudit(String id){try{return Objects.requireNonNull(audit.read(id));}catch(RuntimeException e){return new AuditProjectionClient.AuditProjection(false,0,List.of());}}
    private static int roleOrder(String role){return switch(role){case "approver"->0;case "legal"->1;case "security"->2;case "registrar"->3;default->4;};}
    private record Local(String versionId,boolean immutable,long documentSequence){}
}
