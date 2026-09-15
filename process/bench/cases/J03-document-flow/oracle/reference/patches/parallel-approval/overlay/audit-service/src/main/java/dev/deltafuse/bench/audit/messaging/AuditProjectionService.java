package dev.deltafuse.bench.audit.messaging;

import dev.deltafuse.bench.contracts.*;
import java.sql.*;
import javax.sql.DataSource;

/** Reference projection accepts baseline plus target workflow payloads. */
public final class AuditProjectionService {
    private final DataSource dataSource;
    public AuditProjectionService(DataSource dataSource){this.dataSource=dataSource;}

    public boolean consume(String wireEvent) {
        JsonObj event;
        try {
            event=CanonicalJson.parse(wireEvent).asObj();
            event.requireClosed("schema_name","schema_version","event_id","producer",
                    "aggregate_type","aggregate_id","domain_sequence","correlation_id",
                    "causation_id","occurred_at","payload");
        } catch (IllegalArgumentException failure) {
            throw new ContractViolation(ErrorCode.INVALID_SCHEMA,"malformed event JSON");
        }
        String schema=event.getString("schema_name");
        if(event.getLong("schema_version")!=1)throw new ContractViolation(ErrorCode.INVALID_SCHEMA,"unknown schema version");
        String eventId=event.getString("event_id");
        String aggregateType=AggregateType.parse(event.getString("aggregate_type")).name();
        String aggregateId=event.getString("aggregate_id");
        long domainSequence=event.getLong("domain_sequence");
        event.getString("producer"); event.getString("correlation_id");
        event.getOptionalString("causation_id"); event.getOptionalString("occurred_at");
        JsonObj payload=event.member("payload").asObj();
        String documentId=payload.getString("document_id");
        String canonical=CanonicalJson.write(event);
        try(Connection connection=dataSource.getConnection()){
            connection.setAutoCommit(false);
            try{
                String prior=prior(connection,eventId);
                if(prior!=null){Idempotency.requireSamePayload(eventId,prior,canonical);connection.commit();return false;}
                update(connection,"INSERT INTO inbox_event(event_id,event_payload) VALUES (?,?::jsonb)",eventId,canonical);
                update(connection,"INSERT INTO audit_event(event_id,document_id,sequence,kind,payload,aggregate_type,aggregate_id) VALUES (?,?,?,?,?::jsonb,?,?)",
                        eventId,documentId,stableSequence(domainSequence,schema),schema,
                        CanonicalJson.write(payload),aggregateType,aggregateId);
                connection.commit();return true;
            }catch(RuntimeException failure){connection.rollback();throw failure;}
            catch(SQLException failure){connection.rollback();throw new IllegalStateException("audit projection transaction failed",failure);}
        }catch(SQLException failure){throw new IllegalStateException("audit projection unavailable",failure);}
    }

    private static long stableSequence(long sequence,String schema){
        int rank=switch(schema){
            case "j03.document.created"->0;
            case "j03.document.version-created"->1;
            case "j03.document.version-submitted"->2;
            case "j03.workflow.route-created"->3;
            case "j03.workflow.decision-applied"->4;
            case "j03.workflow.route-superseded"->5;
            case "j03.workflow.decision-ignored"->6;
            default->9;
        };
        return Math.multiplyExact(sequence,10L)+rank;
    }
    private static String prior(Connection c,String id)throws SQLException{try(var s=c.prepareStatement("SELECT event_payload::text FROM inbox_event WHERE event_id=?")){s.setString(1,id);try(var r=s.executeQuery()){return r.next()?CanonicalJson.write(CanonicalJson.parse(r.getString(1))):null;}}}
    private static void update(Connection c,String sql,Object...values)throws SQLException{try(var s=c.prepareStatement(sql)){for(int i=0;i<values.length;i++)s.setObject(i+1,values[i]);s.executeUpdate();}}
}
