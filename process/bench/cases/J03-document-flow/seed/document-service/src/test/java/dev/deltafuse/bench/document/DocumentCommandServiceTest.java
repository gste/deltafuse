package dev.deltafuse.bench.document;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import dev.deltafuse.bench.contracts.ErrorCode;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.UUID;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.postgresql.ds.PGSimpleDataSource;
import org.testcontainers.containers.PostgreSQLContainer;

@Tag("db-integration")
class DocumentCommandServiceTest {

    private static PostgreSQLContainer<?> postgres;
    private static PGSimpleDataSource dataSource;
    private DocumentCommandService commands;

    @BeforeAll
    static void startDatabase() {
        postgres = new PostgreSQLContainer<>("postgres:17.6");
        postgres.start();
        dataSource = new PGSimpleDataSource();
        dataSource.setURL(postgres.getJdbcUrl());
        dataSource.setUser(postgres.getUsername());
        dataSource.setPassword(postgres.getPassword());
        Flyway.configure().dataSource(dataSource).load().migrate();
    }

    @AfterAll
    static void stopDatabase() {
        if (postgres != null) {
            postgres.stop();
        }
    }

    @BeforeEach
    void resetDatabase() throws SQLException {
        try (Connection connection = dataSource.getConnection(); Statement statement = connection.createStatement()) {
            statement.execute("TRUNCATE command_receipt, outbox_event, document_version, document CASCADE");
        }
        commands = new DocumentCommandService(dataSource);
    }

    @Test
    void create_document_writes_draft_receipt_and_outbox_atomically() throws SQLException {
        CommandResult result = commands.createDocument("op-1", "evt-1", "doc-1", "Policy");
        assertEquals(new CommandResult("op-1", "doc-1", null, "DRAFT", "evt-1", 1), result);
        assertEquals(1, count("document"));
        assertEquals(1, count("command_receipt"));
        assertEquals(1, count("outbox_event"));
        assertEquals("j03.document.created", scalar("SELECT schema_name FROM outbox_event"));
    }

    @Test
    void exact_create_replay_returns_prior_result_without_another_effect() throws SQLException {
        CommandResult first = commands.createDocument("op-2", "evt-2", "doc-2", "Policy");
        CommandResult replay = commands.createDocument("op-2", "evt-2", "doc-2", "Policy");
        assertEquals(first, replay);
        assertEquals(1, count("document"));
        assertEquals(1, count("outbox_event"));
    }

    @Test
    void operation_key_with_different_payload_is_a_conflict() {
        commands.createDocument("op-3", "evt-3", "doc-3", "Policy");
        DocumentFailure failure = assertThrows(DocumentFailure.class,
                () -> commands.createDocument("op-3", "evt-3", "doc-3", "Changed"));
        assertEquals(ErrorCode.IDEMPOTENCY_CONFLICT, failure.code());
        assertEquals("op-3", failure.operationId());
    }

    @Test
    void duplicate_version_command_never_creates_a_second_version() throws SQLException {
        commands.createDocument("op-4a", "evt-4a", "doc-4", "Policy");
        CommandResult first = commands.createVersion("op-4b", "evt-4b", "doc-4", "ver-4", "body");
        CommandResult replay = commands.createVersion("op-4b", "evt-4b", "doc-4", "ver-4", "body");
        assertEquals(first, replay);
        assertEquals(1, count("document_version"));
        assertEquals(2, count("outbox_event"));
    }

    @Test
    void missing_document_rejects_version_without_partial_effect() throws SQLException {
        DocumentFailure failure = assertThrows(DocumentFailure.class,
                () -> commands.createVersion("op-5", "evt-5", "missing", "ver-5", "body"));
        assertEquals(ErrorCode.DOCUMENT_NOT_FOUND, failure.code());
        assertEquals(0, count("command_receipt"));
        assertEquals(0, count("outbox_event"));
    }

    @Test
    void submit_makes_version_immutable_and_emits_one_event() throws SQLException {
        commands.createDocument("op-6a", "evt-6a", "doc-6", "Policy");
        commands.createVersion("op-6b", "evt-6b", "doc-6", "ver-6", "body");
        CommandResult result = commands.submitVersion("op-6c", "evt-6c", "doc-6", "ver-6");
        assertEquals("SUBMITTED", result.state());
        assertEquals("SUBMITTED", scalar("SELECT state FROM document_version WHERE version_id='ver-6'"));
        assertEquals("j03.document.version-submitted",
                scalar("SELECT schema_name FROM outbox_event WHERE event_id='evt-6c'"));
        DocumentFailure second = assertThrows(DocumentFailure.class,
                () -> commands.submitVersion("op-6d", "evt-6d", "doc-6", "ver-6"));
        assertEquals(ErrorCode.VERSION_IMMUTABLE, second.code());
        assertEquals(3, count("outbox_event"));
    }

    @Test
    void forced_failure_rolls_back_new_version_receipt_and_outbox() throws SQLException {
        commands.createDocument("op-7a", "evt-7a", "doc-7", "Policy");
        DocumentCommandService failing = new DocumentCommandService(dataSource,
                connection -> { throw new IllegalStateException("forced-before-commit"); });
        assertThrows(IllegalStateException.class,
                () -> failing.createVersion("op-7b", "evt-7b", "doc-7", "ver-7", "body"));
        assertEquals(0, count("document_version"));
        assertEquals(1, count("command_receipt"));
        assertEquals(1, count("outbox_event"));
    }

    @Test
    void forced_failure_before_submit_commit_restores_draft_and_no_outbox() throws SQLException {
        commands.createDocument("op-8a", "evt-8a", "doc-8", "Policy");
        commands.createVersion("op-8b", "evt-8b", "doc-8", "ver-8", "body");
        DocumentCommandService failing = new DocumentCommandService(dataSource,
                connection -> { throw new IllegalStateException("forced-before-commit"); });
        assertThrows(IllegalStateException.class,
                () -> failing.submitVersion("op-8c", "evt-8c", "doc-8", "ver-8"));
        assertEquals("DRAFT", scalar("SELECT state FROM document_version WHERE version_id='ver-8'"));
        assertEquals(2, count("command_receipt"));
        assertEquals(2, count("outbox_event"));
    }

    private static long count(String table) throws SQLException {
        return ((Number) scalar("SELECT count(*) FROM " + table)).longValue();
    }

    private static Object scalar(String sql) throws SQLException {
        try (Connection connection = dataSource.getConnection(); Statement statement = connection.createStatement();
                ResultSet rows = statement.executeQuery(sql)) {
            rows.next();
            return rows.getObject(1);
        }
    }
}
