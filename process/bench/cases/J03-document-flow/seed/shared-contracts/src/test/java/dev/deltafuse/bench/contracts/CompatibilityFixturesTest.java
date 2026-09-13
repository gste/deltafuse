package dev.deltafuse.bench.contracts;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;

/**
 * Validates the published public compatibility fixtures under
 * {@code seed/docs/spec/contracts/fixtures}. Valid fixtures must decode and
 * re-encode byte-identically; invalid fixtures must fail with the error code
 * declared as the file name prefix ({@code CODE__description.json}).
 */
class CompatibilityFixturesTest {

    private static final Path FIXTURES = Path.of("..", "docs", "spec", "contracts", "fixtures", "events");

    @Test
    void valid_fixtures_decode_and_reencode_identically() throws IOException {
        try (Stream<Path> files = sortedFixtureFiles(FIXTURES.resolve("valid"))) {
            assertTrue(files.findAny().isPresent(), "no valid fixtures published");
        }
        try (Stream<Path> files = sortedFixtureFiles(FIXTURES.resolve("valid"))) {
            files.forEach(path -> {
                String raw = read(path).stripTrailing();
                BaselineEvents.Decoded decoded = BaselineEvents.decode(raw);
                String reencoded = BaselineEvents.encode(decoded.envelope(), decoded.payload().toJson());
                assertEquals(raw, reencoded, "fixture is not canonical: " + path);
            });
        }
    }

    @Test
    void invalid_fixtures_fail_with_the_declared_error_code() throws IOException {
        try (Stream<Path> files = sortedFixtureFiles(FIXTURES.resolve("invalid"))) {
            assertTrue(files.findAny().isPresent(), "no invalid fixtures published");
        }
        try (Stream<Path> files = sortedFixtureFiles(FIXTURES.resolve("invalid"))) {
            files.forEach(path -> {
                String name = path.getFileName().toString();
                String declared = name.substring(0, name.indexOf("__"));
                ErrorCode expected = ErrorCode.valueOf(declared);
                ContractViolation violation = assertThrows(ContractViolation.class,
                        () -> BaselineEvents.decode(read(path)),
                        "fixture should fail with " + expected + ": " + name);
                assertEquals(expected, violation.code(), name);
            });
        }
    }

    private static Stream<Path> sortedFixtureFiles(Path directory) throws IOException {
        if (!Files.isDirectory(directory)) {
            return Stream.empty();
        }
        try (Stream<Path> files = Files.list(directory)) {
            return files
                    .filter(path -> path.getFileName().toString().endsWith(".json"))
                    .sorted(Comparator.comparing(path -> path.getFileName().toString()))
                    .toList()
                    .stream();
        }
    }

    private static String read(Path path) {
        try {
            return Files.readString(path);
        } catch (IOException e) {
            throw new IllegalStateException("cannot read fixture " + path, e);
        }
    }
}
