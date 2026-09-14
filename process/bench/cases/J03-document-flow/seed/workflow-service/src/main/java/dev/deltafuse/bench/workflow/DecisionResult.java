package dev.deltafuse.bench.workflow;

import com.fasterxml.jackson.annotation.JsonProperty;

public record DecisionResult(
        @JsonProperty("operation_id") String operationId,
        @JsonProperty("route_id") String routeId,
        @JsonProperty("decision_id") String decisionId,
        String state,
        @JsonProperty("event_id") String eventId,
        @JsonProperty("domain_sequence") long domainSequence) {
}
