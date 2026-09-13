package dev.deltafuse.bench.contracts;

/** JSON 64-bit signed integer; the only number type of the baseline contracts. */
public record JsonNum(long value) implements JsonValue {
}
