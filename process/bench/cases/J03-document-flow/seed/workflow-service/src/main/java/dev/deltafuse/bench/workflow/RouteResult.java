package dev.deltafuse.bench.workflow;

import com.fasterxml.jackson.annotation.JsonProperty;

public record RouteResult(
        @JsonProperty("route_id") String routeId,
        @JsonProperty("document_id") String documentId,
        @JsonProperty("version_id") String versionId,
        @JsonProperty("approver_actor_id") String approverActorId,
        String state,
        @JsonProperty("event_id") String eventId,
        @JsonProperty("domain_sequence") long domainSequence) {
}
