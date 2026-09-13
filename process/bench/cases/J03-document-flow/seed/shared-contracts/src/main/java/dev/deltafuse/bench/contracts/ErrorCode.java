package dev.deltafuse.bench.contracts;

/**
 * A closed public contract vocabulary for baseline API errors. Status codes
 * follow the frozen public contract: 400 for schema/identity/action
 * rejections, 404 for missing entities, 409 for immutability and
 * idempotency conflicts. Target-change codes (for example actor/role
 * mismatch or incomplete expert review) are deliberately absent until the
 * target Change introduces them.
 */
public enum ErrorCode {
    INVALID_SCHEMA(400),
    IDENTITY_MISMATCH(400),
    UNSUPPORTED_ACTION(400),
    DOCUMENT_NOT_FOUND(404),
    VERSION_NOT_FOUND(404),
    VERSION_IMMUTABLE(409),
    IDEMPOTENCY_CONFLICT(409);

    private final int httpStatus;

    ErrorCode(int httpStatus) {
        this.httpStatus = httpStatus;
    }

    public int httpStatus() {
        return httpStatus;
    }

    public static ErrorCode parse(String value) {
        try {
            return ErrorCode.valueOf(value);
        } catch (IllegalArgumentException | NullPointerException e) {
            throw new ContractViolation(ErrorCode.INVALID_SCHEMA, "unknown error code: " + value);
        }
    }
}
