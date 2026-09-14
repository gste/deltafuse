package dev.deltafuse.bench.document;

import dev.deltafuse.bench.contracts.ErrorCode;
import java.util.Objects;

/** Public command rejection with the operation identity needed by the API error body. */
public final class DocumentFailure extends RuntimeException {
    private final ErrorCode code;
    private final String operationId;

    public DocumentFailure(ErrorCode code, String operationId, String message) {
        super(message);
        this.code = Objects.requireNonNull(code, "code");
        this.operationId = operationId;
    }

    public ErrorCode code() {
        return code;
    }

    public String operationId() {
        return operationId;
    }
}
