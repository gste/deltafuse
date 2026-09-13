package dev.deltafuse.bench.contracts;

import java.util.Objects;

/** Validation helpers for opaque public identifiers and bounded text. */
public final class Identifiers {

    private static final int MAX_ID_LENGTH = 128;

    private Identifiers() {
    }

    /** Non-empty opaque identifier, at most 128 chars, without control characters. */
    public static String require(String field, String value) {
        if (value == null || value.isEmpty()) {
            throw new ContractViolation(ErrorCode.INVALID_SCHEMA, field + " is required");
        }
        if (value.length() > MAX_ID_LENGTH) {
            throw new ContractViolation(ErrorCode.INVALID_SCHEMA,
                    field + " exceeds " + MAX_ID_LENGTH + " characters");
        }
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (c <= 0x1F || c == 0x7F) {
                throw new ContractViolation(ErrorCode.INVALID_SCHEMA,
                        field + " must not contain control characters");
            }
        }
        return value;
    }

    /** Non-empty text with an explicit maximum length; control characters rejected. */
    public static String requireText(String field, String value, int maxLength) {
        require(field, value);
        if (value.length() > maxLength) {
            throw new ContractViolation(ErrorCode.INVALID_SCHEMA,
                    field + " exceeds " + maxLength + " characters");
        }
        return value;
    }

    public static String requireProducer(String value) {
        return Objects.requireNonNull(require("producer", value));
    }
}
