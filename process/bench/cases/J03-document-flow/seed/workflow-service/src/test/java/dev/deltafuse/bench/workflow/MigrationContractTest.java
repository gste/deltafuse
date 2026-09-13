package dev.deltafuse.bench.workflow;

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
 * Migration contract of the workflow service baseline schema, proven on a
 * real pinned PostgreSQL: fresh install, route and decision identity
 * constraints, closed vocabularies (including the rejection of any target
 * multi-stage value such as {@code SUPERSEDED} or the {@code registrar}
 * role), judge read-only access, cross-service connection denial, idempotent
 * re-migration and the applied-migration checksum guard. Tagged
 * {@code db-integration}; runs only under the {@code db-integration} Maven
 * profile.
 */
@Tag("db-integration")
class MigrationContractTest {

    private static final String IMAGE = "postgres:17.6";
    private static final Path INIT = Path.of("..", "infra", "postgres", "init");
    private static final Path GRANTS = Path.of("..", "infra", "postgres", "grants");

    private static PostgreSQLContainer<?> postgres;
    private static String workflowPassword;
    private static String judgePassword;

    @BeforeAll
    static void provisionClusterAndMigrate() throws Exception {
        postgres = new PostgreSQLContainer<>(IMAGE);
        postgres.start();
        workflowPassword = randomPassword();
        judgePassword = randomPassword();
        try (Connection superuser = superuserConnection()) {
            runSql(superuser, INIT.resolve("00-roles.sql"));
            exec(superuser, "ALTER ROLE j03_workflow_app LOGIN PASSWORD '" + workflowPassword + "'");
            exec(superuser, "ALTER ROLE j03_judge_readonly LOGIN PASSWORD '" + judgePassword + "'");
            runSql(superuser, INIT.resolve("01-databases.sql"));
        }
        Flyway.configure()
                .dataSource(url("j03_workflow"), "j03_workflow_app", workflowPassword)
                .load()
                .migrate();
        try (Connection owner = ownerConnection()) {
            runSql(owner, GRANTS.resolve("j03_workflow.sql"));
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
                        "route", "decision", "outbox_event", "inbox_event", "flyway_schema_history")),
                "missing baseline tables in " + tables);
    }

    @Test
    void route_identity_is_unique_per_document_and_version() throws SQLException {
        exec(owner(), "INSERT INTO route (route_id, document_id, version_id, approver_actor_id, state) "
                + "VALUES ('mig-rte-1', 'mig-doc-1', 'mig-ver-1', 'mig-usr-1', 'PENDING')");
        SQLException violation = assertThrows(SQLException.class,
                () -> exec(owner(), "INSERT INTO route (route_id, document_id, version_id, approver_actor_id, state) "
                        + "VALUES ('mig-rte-1b', 'mig-doc-1', 'mig-ver-1', 'mig-usr-1', 'PENDING')"));
        assertEquals("23505", violation.getSQLState());
    }

    @Test
    void decision_id_is_the_idempotency_key_within_a_route() throws SQLException {
        exec(owner(), "INSERT INTO route (route_id, document_id, version_id, approver_actor_id, state) "
                + "VALUES ('mig-rte-2', 'mig-doc-2', 'mig-ver-2', 'mig-usr-2', 'PENDING')");
        String insert = "INSERT INTO decision (route_id, decision_id, actor_id, role, action, resulting_state) "
                + "VALUES ('mig-rte-2', 'mig-dec-1', 'mig-usr-2', 'approver', 'APPROVE', 'APPROVED')";
        exec(owner(), insert);
        SQLException violation = assertThrows(SQLException.class, () -> exec(owner(), insert));
        assertEquals("23505", violation.getSQLState());
    }

    @Test
    void route_state_vocabulary_is_closed() throws SQLException {
        SQLException violation = assertThrows(SQLException.class,
                () -> exec(owner(), "INSERT INTO route (route_id, document_id, version_id, approver_actor_id, state) "
                        + "VALUES ('mig-rte-3', 'mig-doc-3', 'mig-ver-3', 'mig-usr-3', 'SUPERSEDED')"));
        assertEquals("23514", violation.getSQLState());
    }

    @Test
    void decision_role_vocabulary_is_closed() throws SQLException {
        exec(owner(), "INSERT INTO route (route_id, document_id, version_id, approver_actor_id, state) "
                + "VALUES ('mig-rte-4', 'mig-doc-4', 'mig-ver-4', 'mig-usr-4', 'PENDING')");
        SQLException violation = assertThrows(SQLException.class,
                () -> exec(owner(), "INSERT INTO decision (route_id, decision_id, actor_id, role, action, resulting_state) "
                        + "VALUES ('mig-rte-4', 'mig-dec-2', 'mig-usr-9', 'registrar', 'APPROVE', 'APPROVED')"));
        assertEquals("23514", violation.getSQLState());
    }

    @Test
    void decision_action_vocabulary_is_closed() throws SQLException {
        SQLException violation = assertThrows(SQLException.class,
                () -> exec(owner(), "INSERT INTO decision (route_id, decision_id, actor_id, role, action, resulting_state) "
                        + "VALUES ('mig-rte-4', 'mig-dec-3', 'mig-usr-4', 'approver', 'ESCALATE', 'APPROVED')"));
        assertEquals("23514", violation.getSQLState());
    }

    @Test
    void decision_resulting_state_vocabulary_is_closed() throws SQLException {
        SQLException violation = assertThrows(SQLException.class,
                () -> exec(owner(), "INSERT INTO decision (route_id, decision_id, actor_id, role, action, resulting_state) "
                        + "VALUES ('mig-rte-4', 'mig-dec-4', 'mig-usr-4', 'approver', 'APPROVE', 'SUPERSEDED')"));
        assertEquals("23514", violation.getSQLState());
    }

    @Test
    void outbox_sequence_is_unique_per_aggregate() throws SQLException {
        String insert = "INSERT INTO outbox_event (event_id, aggregate_type, aggregate_id, "
                + "domain_sequence, schema_name, schema_version, payload) "
                + "VALUES ('%s', 'ROUTE', 'mig-rte-5', 1, 'j03.workflow.route-created', 1, '{}'::jsonb)";
        exec(owner(), String.format(insert, "mig-oe-1"));
        SQLException violation = assertThrows(SQLException.class,
                () -> exec(owner(), String.format(insert, "mig-oe-2")));
        assertEquals("23505", violation.getSQLState());
    }

    @Test
    void judge_role_can_read_but_never_write() throws SQLException {
        try (Connection judge = DriverManager.getConnection(url("j03_workflow"),
                "j03_judge_readonly", judgePassword)) {
            exec(judge, "SELECT count(*) FROM route");
            SQLException write = assertThrows(SQLException.class,
                    () -> exec(judge, "INSERT INTO route (route_id, document_id, version_id, approver_actor_id, state) "
                            + "VALUES ('mig-rte-j', 'mig-doc-j', 'mig-ver-j', 'mig-usr-j', 'PENDING')"));
            assertEquals("42501", write.getSQLState());
        }
    }

    @Test
    void workflow_owner_cannot_open_other_service_databases() {
        for (String other : new String[] {"j03_document", "j03_audit"}) {
            SQLException denied = assertThrows(SQLException.class,
                    () -> DriverManager.getConnection(url(other), "j03_workflow_app", workflowPassword));
            assertEquals("42501", denied.getSQLState());
        }
    }

    @Test
    void re_running_migrations_is_idempotent_and_validates() {
        Flyway flyway = Flyway.configure()
                .dataSource(url("j03_workflow"), "j03_workflow_app", workflowPassword)
                .load();
        assertEquals(0, flyway.migrate().migrationsExecuted, "second migrate must be a no-op");
        flyway.validate();
    }

    @Test
    void changed_applied_migration_fails_validation() throws Exception {
        Path tampered = Files.createTempDirectory("j03-workflow-migrations");
        Path source = Path.of("target", "classes", "db", "migration", "V1__baseline_workflow_schema.sql");
        try (Stream<Path> migrations = Files.list(Path.of("target", "classes", "db", "migration"))) {
            for (Path migration : migrations.toList()) {
                Files.copy(migration, tampered.resolve(migration.getFileName()));
            }
        }
        Files.writeString(tampered.resolve("V1__baseline_workflow_schema.sql"),
                Files.readString(source) + "\n-- tampered\n");
        FlywayException failure = assertThrows(FlywayException.class,
                () -> Flyway.configure()
                        .locations("filesystem:" + tampered.toString())
                        .dataSource(url("j03_workflow"), "j03_workflow_app", workflowPassword)
                        .load()
                        .validate());
        assertTrue(failure.getMessage().toLowerCase().contains("checksum"), failure.getMessage());
    }

    private static Connection superuserConnection() throws SQLException {
        return DriverManager.getConnection(postgres.getJdbcUrl(), postgres.getUsername(), postgres.getPassword());
    }

    private static Connection ownerConnection() throws SQLException {
        return DriverManager.getConnection(url("j03_workflow"), "j03_workflow_app", workflowPassword);
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
