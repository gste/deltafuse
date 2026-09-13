package dev.deltafuse.bench.contracts;

import java.util.List;
import java.util.TreeMap;

/**
 * Strict JSON parsing and deterministic canonical serialization.
 *
 * <p>The parser accepts the RFC 8259 subset used by the baseline contracts
 * and rejects everything else: duplicate object keys, raw control characters
 * in strings, non-integer or malformed numbers, {@code NaN}/{@code Infinity}
 * literals, invalid escapes, trailing content and excessive nesting. The
 * writer emits one canonical form: members sorted lexicographically, no
 * whitespace, minimal escaping with lowercase {@code \\u00xx} for the
 * remaining control characters. Canonical bytes are the payload-equality
 * basis of the idempotency contract.
 */
public final class CanonicalJson {

    private static final int MAX_DEPTH = 64;

    private CanonicalJson() {
    }

    public static JsonValue parse(String source) {
        Parser parser = new Parser(source);
        JsonValue value = parser.parseValue(0);
        parser.skipWhitespace();
        if (!parser.atEnd()) {
            throw parser.error("trailing content");
        }
        return value;
    }

    public static String write(JsonValue value) {
        StringBuilder out = new StringBuilder();
        writeValue(value, out);
        return out.toString();
    }

    private static void writeValue(JsonValue value, StringBuilder out) {
        if (value instanceof JsonNull) {
            out.append("null");
        } else if (value instanceof JsonBool bool) {
            out.append(bool.value() ? "true" : "false");
        } else if (value instanceof JsonNum num) {
            out.append(num.value());
        } else if (value instanceof JsonStr str) {
            writeString(str.value(), out);
        } else if (value instanceof JsonArr arr) {
            out.append('[');
            for (int i = 0; i < arr.items().size(); i++) {
                if (i > 0) {
                    out.append(',');
                }
                writeValue(arr.items().get(i), out);
            }
            out.append(']');
        } else if (value instanceof JsonObj obj) {
            out.append('{');
            boolean first = true;
            for (var entry : obj.members().entrySet()) {
                if (!first) {
                    out.append(',');
                }
                first = false;
                writeString(entry.getKey(), out);
                out.append(':');
                writeValue(entry.getValue(), out);
            }
            out.append('}');
        } else {
            throw new IllegalArgumentException("unsupported JSON value: " + value.getClass());
        }
    }

    private static void writeString(String value, StringBuilder out) {
        out.append('"');
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\b' -> out.append("\\b");
                case '\f' -> out.append("\\f");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
                }
            }
        }
        out.append('"');
    }

    private static final class Parser {
        private final String source;
        private int pos;

        Parser(String source) {
            this.source = source;
        }

        IllegalArgumentException error(String message) {
            return new IllegalArgumentException("invalid JSON at offset " + pos + ": " + message);
        }

        boolean atEnd() {
            return pos >= source.length();
        }

        void skipWhitespace() {
            while (!atEnd()) {
                char c = source.charAt(pos);
                if (c == ' ' || c == '\t' || c == '\n' || c == '\r') {
                    pos++;
                } else {
                    return;
                }
            }
        }

        JsonValue parseValue(int depth) {
            if (depth > MAX_DEPTH) {
                throw error("nesting too deep");
            }
            skipWhitespace();
            if (atEnd()) {
                throw error("unexpected end of input");
            }
            char c = source.charAt(pos);
            return switch (c) {
                case '{' -> parseObject(depth);
                case '[' -> parseArray(depth);
                case '"' -> new JsonStr(parseString());
                case 't' -> parseLiteral("true", new JsonBool(true));
                case 'f' -> parseLiteral("false", new JsonBool(false));
                case 'n' -> parseLiteral("null", JsonNull.INSTANCE);
                default -> parseNumber();
            };
        }

        private JsonValue parseLiteral(String literal, JsonValue value) {
            if (!source.startsWith(literal, pos)) {
                throw error("invalid literal");
            }
            pos += literal.length();
            return value;
        }

        private JsonValue parseObject(int depth) {
            pos++;
            skipWhitespace();
            TreeMap<String, JsonValue> members = new TreeMap<>();
            if (!atEnd() && source.charAt(pos) == '}') {
                pos++;
                return new JsonObj(members);
            }
            while (true) {
                skipWhitespace();
                if (atEnd() || source.charAt(pos) != '"') {
                    throw error("expected object key");
                }
                String key = parseString();
                if (members.containsKey(key)) {
                    throw error("duplicate object key");
                }
                skipWhitespace();
                if (atEnd() || source.charAt(pos) != ':') {
                    throw error("expected ':'");
                }
                pos++;
                members.put(key, parseValue(depth + 1));
                skipWhitespace();
                if (atEnd()) {
                    throw error("unterminated object");
                }
                char c = source.charAt(pos);
                if (c == ',') {
                    pos++;
                    continue;
                }
                if (c == '}') {
                    pos++;
                    return new JsonObj(members);
                }
                throw error("expected ',' or '}'");
            }
        }

        private JsonValue parseArray(int depth) {
            pos++;
            skipWhitespace();
            java.util.List<JsonValue> items = new java.util.ArrayList<>();
            if (!atEnd() && source.charAt(pos) == ']') {
                pos++;
                return new JsonArr(items);
            }
            while (true) {
                items.add(parseValue(depth + 1));
                skipWhitespace();
                if (atEnd()) {
                    throw error("unterminated array");
                }
                char c = source.charAt(pos);
                if (c == ',') {
                    pos++;
                    continue;
                }
                if (c == ']') {
                    pos++;
                    return new JsonArr(items);
                }
                throw error("expected ',' or ']'");
            }
        }

        private String parseString() {
            pos++;
            StringBuilder out = new StringBuilder();
            while (true) {
                if (atEnd()) {
                    throw error("unterminated string");
                }
                char c = source.charAt(pos);
                if (c == '"') {
                    pos++;
                    return out.toString();
                }
                if (c < 0x20) {
                    throw error("raw control character in string");
                }
                if (c != '\\') {
                    out.append(c);
                    pos++;
                    continue;
                }
                pos++;
                if (atEnd()) {
                    throw error("unterminated escape");
                }
                char esc = source.charAt(pos++);
                switch (esc) {
                    case '"' -> out.append('"');
                    case '\\' -> out.append('\\');
                    case '/' -> out.append('/');
                    case 'b' -> out.append('\b');
                    case 'f' -> out.append('\f');
                    case 'n' -> out.append('\n');
                    case 'r' -> out.append('\r');
                    case 't' -> out.append('\t');
                    case 'u' -> out.append(parseUnicodeEscape());
                    default -> throw error("invalid escape \\" + esc);
                }
            }
        }

        private char parseUnicodeEscape() {
            if (pos + 4 > source.length()) {
                throw error("truncated unicode escape");
            }
            String hex = source.substring(pos, pos + 4);
            pos += 4;
            try {
                return (char) Integer.parseInt(hex, 16);
            } catch (NumberFormatException e) {
                throw error("invalid unicode escape");
            }
        }

        private JsonValue parseNumber() {
            int start = pos;
            if (!atEnd() && source.charAt(pos) == '-') {
                pos++;
            }
            if (atEnd()) {
                throw error("invalid number");
            }
            char first = source.charAt(pos);
            if (first == '0') {
                pos++;
            } else if (first >= '1' && first <= '9') {
                while (!atEnd() && Character.isDigit(source.charAt(pos))) {
                    pos++;
                }
            } else {
                throw error("invalid number");
            }
            if (!atEnd()) {
                char c = source.charAt(pos);
                if (c == '.' || c == 'e' || c == 'E') {
                    throw error("non-integer numbers are not part of the baseline contracts");
                }
            }
            try {
                return new JsonNum(Long.parseLong(source.substring(start, pos)));
            } catch (NumberFormatException e) {
                throw error("integer out of 64-bit range");
            }
        }
    }
}
