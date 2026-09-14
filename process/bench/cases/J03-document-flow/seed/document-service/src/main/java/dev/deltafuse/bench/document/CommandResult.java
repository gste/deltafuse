package dev.deltafuse.bench.document;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Stable observable result stored with an idempotent document command. */
public record CommandResult(
        @JsonProperty("operation_id") String operationId,
        @JsonProperty("document_id") String documentId,
        @JsonProperty("version_id") String versionId,
        String state,
        @JsonProperty("event_id") String eventId,
        @JsonProperty("domain_sequence") long domainSequence) {
}
