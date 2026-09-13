package dev.deltafuse.bench.contracts;

import java.util.Objects;

/** JSON string. */
public record JsonStr(String value) implements JsonValue {
    public JsonStr {
        Objects.requireNonNull(value, "string value");
    }
}
