package dev.deltafuse.bench.workflow;

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

@RestController
@RequestMapping("/api/workflows")
public final class WorkflowController {
    private final WorkflowCommandService commands;

    public WorkflowController(WorkflowCommandService commands) { this.commands = commands; }

    @PostMapping("/{routeId}/decisions")
    public DecisionResult decide(@PathVariable("routeId") String routeId, @RequestBody String body) {
        Decoded request = decode(body);
        if (!routeId.equals(request.value().getString("route_id"))) {
            throw new WorkflowFailure(ErrorCode.IDENTITY_MISMATCH, request.operationId(),
                    "path and payload route differ");
        }
        JsonObj value = request.value();
        return commands.decide(request.operationId(), value.getString("event_id"), routeId,
                value.getString("document_id"), value.getString("version_id"), value.getString("decision_id"),
                value.getString("actor_id"), value.getString("role"), value.getString("action"));
    }

    @ExceptionHandler(WorkflowFailure.class)
    public ResponseEntity<Map<String, Object>> failure(WorkflowFailure failure) {
        return ResponseEntity.status(failure.code().httpStatus()).body(Map.of(
                "code", failure.code().name(), "operation_id", failure.operationId(), "details", Map.of()));
    }

    private static Decoded decode(String body) {
        String operationId = "unknown";
        try {
            JsonValue parsed = CanonicalJson.parse(body);
            if (!(parsed instanceof JsonObj object)) {
                throw new WorkflowFailure(ErrorCode.INVALID_SCHEMA, operationId, "request must be an object");
            }
            if (object.member("operation_id") instanceof JsonStr value && !value.value().isEmpty()) {
                operationId = value.value();
            }
            object.requireClosed("operation_id", "event_id", "route_id", "document_id", "version_id",
                    "decision_id", "actor_id", "role", "action");
            return new Decoded(object, object.getString("operation_id"));
        } catch (ContractViolation | IllegalArgumentException failure) {
            throw new WorkflowFailure(ErrorCode.INVALID_SCHEMA, operationId, failure.getMessage());
        }
    }

    private record Decoded(JsonObj value, String operationId) { }
}
