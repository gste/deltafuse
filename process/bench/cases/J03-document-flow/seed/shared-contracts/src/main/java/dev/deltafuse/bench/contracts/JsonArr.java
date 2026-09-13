package dev.deltafuse.bench.contracts;

import java.util.List;

/** JSON array. */
public record JsonArr(List<JsonValue> items) implements JsonValue {
    public JsonArr {
        items = List.copyOf(items);
    }
}
