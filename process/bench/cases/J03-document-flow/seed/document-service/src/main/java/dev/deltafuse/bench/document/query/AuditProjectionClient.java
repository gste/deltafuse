package dev.deltafuse.bench.document.query;
import java.util.List;
@FunctionalInterface
public interface AuditProjectionClient {
    AuditProjection read(String documentId);
    record AuditProjection(boolean available,long sequence,List<AuditEntry> entries){public AuditProjection{entries=List.copyOf(entries);}}
    record AuditEntry(long sequence,String eventId,String kind){}
}
