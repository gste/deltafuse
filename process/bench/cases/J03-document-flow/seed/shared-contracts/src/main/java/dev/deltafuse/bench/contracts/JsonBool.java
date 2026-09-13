package dev.deltafuse.bench.contracts;

/** JSON boolean. JSON booleans are never interchangeable with numbers. */
public record JsonBool(boolean value) implements JsonValue {
}
