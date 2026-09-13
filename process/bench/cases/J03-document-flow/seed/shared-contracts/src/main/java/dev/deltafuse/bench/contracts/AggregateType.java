package dev.deltafuse.bench.contracts;

/**
 * Aggregate kinds that own a monotonic domain sequence in the baseline
 * single-step flow. Target aggregates (for example superseded route pairs)
 * are reserved for the target Change.
 */
public enum AggregateType {
    DOCUMENT,
    ROUTE;

    public static AggregateType parse(String value) {
        for (AggregateType type : values()) {
            if (type.name().equals(value)) {
                return type;
            }
        }
        throw new ContractViolation(ErrorCode.INVALID_SCHEMA, "unknown aggregate type: " + value);
    }
}
