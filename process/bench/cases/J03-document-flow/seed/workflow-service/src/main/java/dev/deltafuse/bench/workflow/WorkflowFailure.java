package dev.deltafuse.bench.workflow;

import dev.deltafuse.bench.contracts.ErrorCode;
import java.util.Objects;

public final class WorkflowFailure extends RuntimeException {
    private final ErrorCode code;
    private final String operationId;

    public WorkflowFailure(ErrorCode code, String operationId, String message) {
        super(message);
        this.code = Objects.requireNonNull(code, "code");
        this.operationId = operationId;
    }

    public ErrorCode code() { return code; }
    public String operationId() { return operationId; }
}
