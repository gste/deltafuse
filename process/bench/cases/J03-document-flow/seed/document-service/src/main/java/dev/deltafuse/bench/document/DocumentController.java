package dev.deltafuse.bench.document;

import dev.deltafuse.bench.contracts.CanonicalJson;
import dev.deltafuse.bench.contracts.ContractViolation;
import dev.deltafuse.bench.contracts.ErrorCode;
import dev.deltafuse.bench.contracts.JsonObj;
import dev.deltafuse.bench.contracts.JsonStr;
import dev.deltafuse.bench.contracts.JsonValue;
import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Thin HTTP adapter for the three baseline document mutations. */
@RestController
@RequestMapping("/api/documents")
public final class DocumentController {
    private final DocumentCommandService commands;

    public DocumentController(DocumentCommandService commands) {
        this.commands = commands;
    }

    @PostMapping
    public CommandResult create(@RequestBody String body) {
        DecodedRequest request = decode(body, "operation_id", "event_id", "document_id", "title");
        return commands.createDocument(request.operationId(), request.value().getString("event_id"),
                request.value().getString("document_id"), request.value().getString("title"));
    }

    @PostMapping("/{documentId}/versions")
    public CommandResult createVersion(
            @PathVariable("documentId") String documentId, @RequestBody String body) {
        DecodedRequest request = decode(body, "operation_id", "event_id", "version_id", "content");
        return commands.createVersion(request.operationId(), request.value().getString("event_id"), documentId,
                request.value().getString("version_id"), request.value().getString("content"));
    }

    @PostMapping("/{documentId}/versions/{versionId}/submit")
    public CommandResult submit(@PathVariable("documentId") String documentId,
            @PathVariable("versionId") String versionId,
            @RequestBody String body) {
        DecodedRequest request = decode(body, "operation_id", "event_id", "document_id", "version_id");
        if (!documentId.equals(request.value().getString("document_id"))
                || !versionId.equals(request.value().getString("version_id"))) {
            throw new DocumentFailure(ErrorCode.IDENTITY_MISMATCH, request.operationId(),
                    "path and payload identity differ");
        }
        return commands.submitVersion(
                request.operationId(), request.value().getString("event_id"), documentId, versionId);
    }

    @ExceptionHandler(DocumentFailure.class)
    public ResponseEntity<Map<String, Object>> failure(DocumentFailure failure) {
        Map<String, Object> body = Map.of(
                "code", failure.code().name(),
                "operation_id", failure.operationId(),
                "details", Map.of());
        return ResponseEntity.status(failure.code().httpStatus()).body(body);
    }

    private static DecodedRequest decode(String body, String... fields) {
        String operationId = "unknown";
        try {
            JsonValue parsed = CanonicalJson.parse(body);
            if (!(parsed instanceof JsonObj object)) {
                throw new DocumentFailure(ErrorCode.INVALID_SCHEMA, operationId, "request must be an object");
            }
            if (object.member("operation_id") instanceof JsonStr value && !value.value().isEmpty()) {
                operationId = value.value();
            }
            object.requireClosed(fields);
            return new DecodedRequest(object, object.getString("operation_id"));
        } catch (ContractViolation | IllegalArgumentException violation) {
            throw new DocumentFailure(ErrorCode.INVALID_SCHEMA, operationId, violation.getMessage());
        }
    }

    private record DecodedRequest(JsonObj value, String operationId) {
    }
}
