package dev.deltafuse.bench.document;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.FlywayException;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.PostgreSQLContainer;

/**
 * Migration contract of the document service baseline schema, proven on a
 * real pinned PostgreSQL: fresh install, identity/deduplication constraints,
 * closed vocabularies, judge read-only access, cross-service connection
 * denial, idempotent re-migration, and the applied-migration checksum guard.
 * Tagged {@code db-integration}; runs only under the {@code db-integration}
 * Maven profile.
 */
@Tag("db-integration")
class MigrationContractTest {

    private static final String IMAGE = "postgres:17.6";
    private static final Path INIT = Path.of("..", "infra", "postgres", "init");
    private static final Path GRANTS = Path.of("..", "infra", "postgres", "grants");

    private static PostgreSQLContainer<?> postgres;
    private static String documentPassword;
    private static String judgePassword;

    @BeforeAll
    static void provisionClusterAndMigrate() throws Exception {
        postgres = new PostgreSQLContainer<>(IMAGE);
        postgres.start();
        documentPassword = randomPassword();
        judgePassword = randomPassword();
        try (Connection superuser = superuserConnection()) {
            runSql(superuser, INIT.resolve("00-roles.sql"));
            exec(superuser, "ALTER ROLE j03_document_app LOGIN PASSWORD '" + documentPassword + "'");
            exec(superuser, "ALTER ROLE j03_judge_readonly LOGIN PASSWORD '" + judgePassword + "'");
            runSql(superuser, INIT.resolve("01-databases.sql"));
        }
        Flyway.configure()
                .dataSource(url("j03_document"), "j03_document_app", documentPassword)
                .load()
                .migrate();
        try (Connection owner = ownerConnection()) {
            runSql(owner, GRANTS.resolve("j03_document.sql"));
        }
    }

    @AfterAll
    static void stopContainer() {
        if (postgres != null) {
            postgres.stop();
        }
    }

    @Test
    void fresh_migration_installs_the_baseline_schema() throws SQLException {
        Set<String> tables = ownerTables();
        assertTrue(tables.containsAll(Set.of(
                        "document", "document_version", "outbox_event", "inbox_event",
                        "flyway_schema_history")),
                "missing baseline tables in " + tables);
    }

    @Test
    void duplicate_document_identity_is_rejected() throws SQLException {
        exec(owner(), "INSERT INTO document (document_id, title) VALUES ('mig-doc-1', 'A')");
        SQLException violation = assertThrows(SQLException.class,
                () -> exec(owner(), "INSERT INTO document (document_id, title) VALUES ('mig-doc-1', 'B')"));
        assertEquals("23505", violation.getSQLState());
    }

    @Test
    void version_identity_is_unique_across_documents() throws SQLException {
        exec(owner(), "INSERT INTO document (document_id, title) VALUES ('mig-doc-2a', 'A')");
        exec(owner(), "INSERT INTO document (document_id, title) VALUES ('mig-doc-2b', 'B')");
        exec(owner(), "INSERT INTO document_version (document_id, version_id, content, state) "
                + "VALUES ('mig-doc-2a', 'mig-ver-1', 'body', 'DRAFT')");
        SQLException violation = assertThrows(SQLException.class,
                () -> exec(owner(), "INSERT INTO document_version (document_id, version_id, content, state) "
                        + "VALUES ('mig-doc-2b', 'mig-ver-1', 'other', 'DRAFT')"));
        assertEquals("23505", violation.getSQLState());
    }

    @Test
    void version_state_vocabulary_is_closed() throws SQLException {
        exec(owner(), "INSERT INTO document (document_id, title) VALUES ('mig-doc-3', 'A')");
        SQLException violation = assertThrows(SQLException.class,
                () -> exec(owner(), "INSERT INTO document_version (document_id, version_id, content, state) "
                        + "VALUES ('mig-doc-3', 'mig-ver-2', 'body', 'MUTATED')"));
        assertEquals("23514", violation.getSQLState());
    }

    @Test
    void outbox_sequence_is_unique_per_aggregate() throws SQLException {
        String insert = "INSERT INTO outbox_event (event_id, aggregate_type, aggregate_id, "
                + "domain_sequence, schema_name, schema_version, payload) "
                + "VALUES ('%s', 'DOCUMENT', 'mig-doc-4', 1, 'j03.document.created', 1, '{}'::jsonb)";
        exec(owner(), String.format(insert, "mig-oe-1"));
        SQLException violation = assertThrows(SQLException.class,
                () -> exec(owner(), String.format(insert, "mig-oe-2")));
        assertEquals("23505", violation.getSQLState());
    }

    @Test
    void judge_role_can_read_but_never_write() throws SQLException {
        try (Connection judge = DriverManager.getConnection(url("j03_document"),
                "j03_judge_readonly", judgePassword)) {
            exec(judge, "SELECT count(*) FROM document");
            SQLException write = assertThrows(SQLException.class,
                    () -> exec(judge, "INSERT INTO document (document_id, title) VALUES ('mig-doc-j', 'X')"));
            assertEquals("42501", write.getSQLState());
            SQLException ddl = assertThrows(SQLException.class,
                    () -> exec(judge, "CREATE TABLE judge_must_not (id int)"));
            assertEquals("42501", ddl.getSQLState());
        }
    }

    @Test
    void document_owner_cannot_open_other_service_databases() {
        for (String other : new String[] {"j03_workflow", "j03_audit"}) {
            SQLException denied = assertThrows(SQLException.class,
                    () -> DriverManager.getConnection(url(other), "j03_document_app", documentPassword));
            assertEquals("42501", denied.getSQLState());
        }
    }

    @Test
    void re_running_migrations_is_idempotent_and_validates() {
        Flyway flyway = Flyway.configure()
                .dataSource(url("j03_document"), "j03_document_app", documentPassword)
                .load();
        assertEquals(0, flyway.migrate().migrationsExecuted, "second migrate must be a no-op");
        flyway.validate();
    }

    @Test
    void changed_applied_migration_fails_validation() throws Exception {
        Path tampered = Files.createTempDirectory("j03-document-migrations");
        Path source = Path.of("target", "classes", "db", "migration", "V1__baseline_document_schema.sql");
        try (Stream<Path> migrations = Files.list(Path.of("target", "classes", "db", "migration"))) {
            for (Path migration : migrations.toList()) {
                Files.copy(migration, tampered.resolve(migration.getFileName()));
            }
        }
        Files.writeString(tampered.resolve("V1__baseline_document_schema.sql"),
                Files.readString(source) + "\n-- tampered\n");
        FlywayException failure = assertThrows(FlywayException.class,
                () -> Flyway.configure()
                        .locations("filesystem:" + tampered.toString())
                        .dataSource(url("j03_document"), "j03_document_app", documentPassword)
                        .load()
                        .validate());
        assertTrue(failure.getMessage().toLowerCase().contains("checksum"), failure.getMessage());
    }

    private static Connection superuserConnection() throws SQLException {
        return DriverManager.getConnection(postgres.getJdbcUrl(), postgres.getUsername(), postgres.getPassword());
    }

    private static Connection ownerConnection() throws SQLException {
        return DriverManager.getConnection(url("j03_document"), "j03_document_app", documentPassword);
    }

    private static Connection owner() throws SQLException {
        return ownerConnection();
    }

    private static String url(String database) {
        return String.format("jdbc:postgresql://%s:%d/%s",
                postgres.getHost(), postgres.getMappedPort(PostgreSQLContainer.POSTGRESQL_PORT), database);
    }

    private static Set<String> ownerTables() throws SQLException {
        Set<String> tables = new HashSet<>();
        try (Statement statement = ownerConnection().createStatement();
                var rows = statement.executeQuery(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")) {
            while (rows.next()) {
                tables.add(rows.getString(1));
            }
        }
        return tables;
    }

    private static void exec(Connection connection, String sql) throws SQLException {
        try (Statement statement = connection.createStatement()) {
            statement.execute(sql);
        }
    }

    private static void runSql(Connection connection, Path file) throws Exception {
        String body = Arrays.stream(Files.readString(file).split("\n"))
                .filter(line -> !line.strip().startsWith("--"))
                .collect(Collectors.joining("\n"));
        for (String chunk : body.split(";")) {
            String sql = chunk.strip();
            if (!sql.isEmpty()) {
                exec(connection, sql);
            }
        }
    }

    private static String randomPassword() {
        return "pw-" + UUID.randomUUID();
    }
}
