package dev.deltafuse.bench.audit.query;

import dev.deltafuse.bench.contracts.*;
import java.sql.*;
import java.util.*;
import javax.sql.DataSource;

/** Deterministic canonical audit trail ordered by domain sequence and event id. */
public final class AuditQueryService {
    private final DataSource dataSource;
    public AuditQueryService(DataSource dataSource){this.dataSource=dataSource;}
    public String trail(String documentId){
        List<JsonValue> entries=new ArrayList<>();
        try(Connection c=dataSource.getConnection();PreparedStatement s=c.prepareStatement("SELECT sequence,event_id,kind FROM audit_event WHERE document_id=? ORDER BY sequence,event_id")){c.setReadOnly(true);s.setString(1,documentId);try(ResultSet r=s.executeQuery()){while(r.next())entries.add(JsonObj.of(Map.of("event_id",new JsonStr(r.getString(2)),"kind",new JsonStr(r.getString(3)),"sequence",new JsonNum(r.getLong(1)))));}}
        catch(SQLException failure){throw new IllegalStateException("audit query unavailable",failure);}
        return CanonicalJson.write(new JsonArr(entries));
    }
}
