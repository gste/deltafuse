package dev.deltafuse.bench.contracts;

/**
 * Typed payload of a baseline event. Payloads are closed: every member is
 * named, typed and validated; unknown members and type mismatches are
 * rejected with {@link ErrorCode#INVALID_SCHEMA}.
 */
public interface Payload extends JsonWritable {
}
