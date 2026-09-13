package dev.deltafuse.bench.contracts;

import java.util.Objects;

/**
 * Raised when a message, envelope or payload violates the published baseline
 * contract. The {@link ErrorCode} is the public rejection class; the message
 * is diagnostic and never part of a scored assertion.
 */
public final class ContractViolation extends RuntimeException {

    private final ErrorCode code;

    public ContractViolation(ErrorCode code, String message) {
        super(message);
        this.code = Objects.requireNonNull(code, "code");
    }

    public ErrorCode code() {
        return code;
    }
}
