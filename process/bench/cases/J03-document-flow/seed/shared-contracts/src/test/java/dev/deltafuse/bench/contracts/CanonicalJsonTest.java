package dev.deltafuse.bench.contracts;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

class CanonicalJsonTest {

    @Test
    void write_is_deterministic_across_member_insertion_order() {
        JsonValue first = CanonicalJson.parse("{\"b\":2,\"a\":1}");
        JsonValue second = CanonicalJson.parse("{\"a\":1,\"b\":2}");
        assertEquals(CanonicalJson.write(first), CanonicalJson.write(second));
        assertEquals("{\"a\":1,\"b\":2}", CanonicalJson.write(first));
    }

    @Test
    void round_trip_preserves_the_parsed_value() {
        String raw = "{\"k\":[1,true,null,\"x\"],\"nested\":{\"z\":\"\\u00e9\",\"a\":-3}}";
        JsonValue reparsed = CanonicalJson.parse(CanonicalJson.write(CanonicalJson.parse(raw)));
        assertEquals(CanonicalJson.write(CanonicalJson.parse(raw)), CanonicalJson.write(reparsed));
    }

    @Test
    void duplicate_object_keys_are_rejected() {
        assertThrows(IllegalArgumentException.class, () -> CanonicalJson.parse("{\"a\":1,\"a\":2}"));
    }

    @Test
    void non_integer_numbers_are_rejected() {
        assertThrows(IllegalArgumentException.class, () -> CanonicalJson.parse("{\"a\":1.5}"));
        assertThrows(IllegalArgumentException.class, () -> CanonicalJson.parse("{\"a\":1e3}"));
    }

    @Test
    void malformed_number_syntax_is_rejected() {
        assertThrows(IllegalArgumentException.class, () -> CanonicalJson.parse("{\"a\":01}"));
        assertThrows(IllegalArgumentException.class, () -> CanonicalJson.parse("{\"a\":+1}"));
        assertThrows(IllegalArgumentException.class, () -> CanonicalJson.parse("{\"a\":.1}"));
        assertThrows(IllegalArgumentException.class, () -> CanonicalJson.parse("{\"a\":1.}"));
    }

    @Test
    void nan_and_infinity_literals_are_rejected() {
        assertThrows(IllegalArgumentException.class, () -> CanonicalJson.parse("{\"a\":NaN}"));
        assertThrows(IllegalArgumentException.class, () -> CanonicalJson.parse("{\"a\":Infinity}"));
        assertThrows(IllegalArgumentException.class, () -> CanonicalJson.parse("{\"a\":-Infinity}"));
    }

    @Test
    void raw_control_characters_in_strings_are_rejected() {
        assertThrows(IllegalArgumentException.class, () -> CanonicalJson.parse("{\"a\":\"x\ny\"}"));
        JsonValue escaped = CanonicalJson.parse("{\"a\":\"x\\ny\"}");
        assertEquals("{\"a\":\"x\\ny\"}", CanonicalJson.write(escaped));
    }

    @Test
    void trailing_content_is_rejected() {
        assertThrows(IllegalArgumentException.class, () -> CanonicalJson.parse("{} {}"));
        assertThrows(IllegalArgumentException.class, () -> CanonicalJson.parse("{\"a\":1}x"));
    }

    @Test
    void invalid_escapes_are_rejected() {
        assertThrows(IllegalArgumentException.class, () -> CanonicalJson.parse("{\"a\":\"\\x41\"}"));
        assertThrows(IllegalArgumentException.class, () -> CanonicalJson.parse("{\"a\":\"\\u00\"}"));
    }
}
