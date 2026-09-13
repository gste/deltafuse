package dev.deltafuse.bench.contracts;

/**
 * Closed JSON value model of the baseline contracts. Objects are sorted,
 * keys are unique, and the only number type is a 64-bit integer; the
 * baseline event schemas contain no floating-point values.
 */
public sealed interface JsonValue permits JsonNull, JsonBool, JsonNum, JsonStr, JsonArr, JsonObj {

    static JsonObj obj() {
        return JsonObj.EMPTY;
    }

    default JsonObj asObj() {
        if (this instanceof JsonObj obj) {
            return obj;
        }
        throw new ContractViolation(ErrorCode.INVALID_SCHEMA, "expected a JSON object");
    }
}
