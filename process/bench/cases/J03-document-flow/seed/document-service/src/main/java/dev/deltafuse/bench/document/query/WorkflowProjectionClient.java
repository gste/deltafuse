package dev.deltafuse.bench.document.query;
import java.util.List;
@FunctionalInterface
public interface WorkflowProjectionClient {
    WorkflowProjection read(String documentId);
    record WorkflowProjection(boolean available,String routeId,String state,long sequence,List<OpenSlot> openSlots){public WorkflowProjection{openSlots=List.copyOf(openSlots);}}
    record OpenSlot(String role,String assignedActorId){}
}
