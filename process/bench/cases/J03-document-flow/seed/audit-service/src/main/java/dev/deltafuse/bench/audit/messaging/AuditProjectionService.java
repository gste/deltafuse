package dev.deltafuse.bench.audit.messaging;

import dev.deltafuse.bench.contracts.*;
import java.sql.*;
import javax.sql.DataSource;

/** Append-only event projection. It is deliberately not a domain-state authority. */
public final class AuditProjectionService {
    private final DataSource dataSource;
    public AuditProjectionService(DataSource dataSource){this.dataSource=dataSource;}

    public boolean consume(String wireEvent) {
        BaselineEvents.Decoded decoded=BaselineEvents.decode(wireEvent);
        String canonical=BaselineEvents.encode(decoded);
        String documentId=documentId(decoded.payload());
        try(Connection connection=dataSource.getConnection()){
            connection.setAutoCommit(false);
            try{
                String prior=prior(connection,decoded.envelope().eventId());
                if(prior!=null){Idempotency.requireSamePayload(decoded.envelope().eventId(),prior,canonical);connection.commit();return false;}
                update(connection,"INSERT INTO inbox_event(event_id,event_payload) VALUES (?,?::jsonb)",decoded.envelope().eventId(),canonical);
                update(connection,"INSERT INTO audit_event(event_id,document_id,sequence,kind,payload,aggregate_type,aggregate_id) VALUES (?,?,?,?,?::jsonb,?,?)",
                        decoded.envelope().eventId(),documentId,stableSequence(decoded),decoded.envelope().schemaName(),
                        CanonicalJson.write(decoded.payload().toJson()),decoded.envelope().aggregateType().name(),decoded.envelope().aggregateId());
                connection.commit();return true;
            }catch(RuntimeException failure){connection.rollback();throw failure;}
            catch(SQLException failure){connection.rollback();throw new IllegalStateException("audit projection transaction failed",failure);}
        }catch(SQLException failure){throw new IllegalStateException("audit projection unavailable",failure);}
    }

    private static long stableSequence(BaselineEvents.Decoded decoded){
        int rank=switch(decoded.envelope().schemaName()){
            case "j03.document.created"->0;
            case "j03.document.version-created"->1;
            case "j03.document.version-submitted"->2;
            case "j03.workflow.route-created"->3;
            case "j03.workflow.decision-applied"->4;
            default->9;
        };
        return Math.multiplyExact(decoded.envelope().domainSequence(),10L)+rank;
    }

    private static String documentId(Payload payload){
        if(payload instanceof DocumentCreated p)return p.documentId();
        if(payload instanceof VersionCreated p)return p.documentId();
        if(payload instanceof VersionSubmitted p)return p.documentId();
        if(payload instanceof RouteCreated p)return p.documentId();
        if(payload instanceof DecisionApplied p)return p.documentId();
        throw new ContractViolation(ErrorCode.INVALID_SCHEMA,"unsupported audit payload");
    }
    private static String prior(Connection c,String id)throws SQLException{try(var s=c.prepareStatement("SELECT event_payload::text FROM inbox_event WHERE event_id=?")){s.setString(1,id);try(var r=s.executeQuery()){return r.next()?CanonicalJson.write(CanonicalJson.parse(r.getString(1))):null;}}}
    private static void update(Connection c,String sql,Object...values)throws SQLException{try(var s=c.prepareStatement(sql)){for(int i=0;i<values.length;i++)s.setObject(i+1,values[i]);s.executeUpdate();}}
}
