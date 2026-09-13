package dev.deltafuse.bench.contracts;

import java.util.Collections;
import java.util.Map;
import java.util.SortedMap;
import java.util.TreeMap;

/**
 * JSON object with sorted, unique member names. Typed decoders use the
 * accessor helpers to enforce closed member sets and exact types; any
 * violation raises {@link ContractViolation} with {@link ErrorCode#INVALID_SCHEMA}.
 */
public record JsonObj(SortedMap<String, JsonValue> members) implements JsonValue {

    public static final JsonObj EMPTY = new JsonObj(new TreeMap<>());

    public JsonObj {
        TreeMap<String, JsonValue> sorted = new TreeMap<>(members);
        members = Collections.unmodifiableSortedMap(sorted);
    }

    public static JsonObj of(Map<String, JsonValue> members) {
        return new JsonObj(new TreeMap<>(members));
    }

    public JsonValue member(String name) {
        return members.get(name);
    }

    /** Rejects any member outside the allowed closed set. */
    public void requireClosed(String... allowed) {
        for (String name : members.keySet()) {
            boolean known = false;
            for (String candidate : allowed) {
                if (candidate.equals(name)) {
                    known = true;
                    break;
                }
            }
            if (!known) {
                throw new ContractViolation(ErrorCode.INVALID_SCHEMA, "unknown member: " + name);
            }
        }
    }

    public String getString(String name) {
        JsonValue value = required(name);
        if (value instanceof JsonStr str) {
            return str.value();
        }
        throw new ContractViolation(ErrorCode.INVALID_SCHEMA, name + " must be a string");
    }

    public String getOptionalString(String name) {
        JsonValue value = members.get(name);
        if (value == null || value instanceof JsonNull) {
            return null;
        }
        if (value instanceof JsonStr str) {
            return str.value();
        }
        throw new ContractViolation(ErrorCode.INVALID_SCHEMA, name + " must be a string or null");
    }

    public long getLong(String name) {
        JsonValue value = required(name);
        if (value instanceof JsonNum num) {
            return num.value();
        }
        throw new ContractViolation(ErrorCode.INVALID_SCHEMA, name + " must be an integer");
    }

    public JsonObj getObj(String name) {
        JsonValue value = required(name);
        if (value instanceof JsonObj obj) {
            return obj;
        }
        throw new ContractViolation(ErrorCode.INVALID_SCHEMA, name + " must be an object");
    }

    private JsonValue required(String name) {
        JsonValue value = members.get(name);
        if (value == null) {
            throw new ContractViolation(ErrorCode.INVALID_SCHEMA, "missing member: " + name);
        }
        return value;
    }
}
