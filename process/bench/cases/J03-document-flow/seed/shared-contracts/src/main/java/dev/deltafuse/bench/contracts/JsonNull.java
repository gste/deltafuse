package dev.deltafuse.bench.contracts;

/** JSON null. */
public record JsonNull() implements JsonValue {
    public static final JsonNull INSTANCE = new JsonNull();
}
