package dev.deltafuse.bench.workflow;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import dev.deltafuse.bench.contracts.AggregateType;
import dev.deltafuse.bench.contracts.EventEnvelope;
import dev.deltafuse.bench.contracts.VersionSubmitted;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.postgresql.ds.PGSimpleDataSource;
import org.testcontainers.containers.PostgreSQLContainer;

/** Live private-reference checks for the J03-304 approval state machine. */
@Tag("db-integration")
class ReferenceApprovalHarness {
    private static PostgreSQLContainer<?> postgres;
    private static PGSimpleDataSource dataSource;
    private WorkflowCommandService commands;

    @BeforeAll static void startDatabase() {
        postgres = new PostgreSQLContainer<>("postgres:17.6");
        postgres.start();
        dataSource = new PGSimpleDataSource();
        dataSource.setURL(postgres.getJdbcUrl());
        dataSource.setUser(postgres.getUsername());
        dataSource.setPassword(postgres.getPassword());
        Flyway.configure().dataSource(dataSource).load().migrate();
    }

    @AfterAll static void stopDatabase() { if (postgres != null) postgres.stop(); }

    @BeforeEach void resetDatabase() throws SQLException {
        try (Connection connection = dataSource.getConnection(); Statement statement = connection.createStatement()) {
            statement.execute("TRUNCATE decision_receipt, route_receipt, decision, outbox_event, inbox_event, route CASCADE");
        }
        commands = new WorkflowCommandService(dataSource);
    }

    @Test void parallel_approval_invalid_evidence_and_replay_match_contract() throws Exception {
        route("normal");
        assertEquals("EXPERT_REVIEW_INCOMPLETE", decide("normal", "d-early", "reg-1", "registrar", "APPROVE"));
        assertEquals("PENDING", state("normal-route"));
        assertEquals("PENDING", decide("normal", "d-legal", "expert-1", "legal", "APPROVE"));
        assertEquals("ACTOR_ROLE_MISMATCH", decide("normal", "d-reuse", "expert-1", "security", "APPROVE"));
        assertEquals(1, count("decision WHERE route_id='normal-route'"));
        assertEquals("PENDING", decide("normal", "d-security", "expert-2", "security", "APPROVE"));
        assertEquals("UNSUPPORTED_ACTION", decide("normal", "d-reg-reject", "reg-1", "registrar", "REJECT"));
        assertEquals("APPROVED", decide("normal", "d-registrar", "reg-1", "registrar", "APPROVE"));
        assertEquals("APPROVED", decide("normal", "d-registrar", "reg-1", "registrar", "APPROVE"));
        assertEquals(3, count("decision WHERE route_id='normal-route'"));
        assertEquals(6, count("decision_receipt WHERE route_id='normal-route'"));

        route("reject");
        assertEquals("REJECTED", decide("reject", "d-reject", "expert-3", "legal", "REJECT"));
        assertThrows(WorkflowFailure.class,
                () -> decide("reject", "d-after", "expert-4", "security", "APPROVE"));
        assertEquals("REJECTED", state("reject-route"));
        assertEquals(1, count("decision WHERE route_id='reject-route'"));

        int generatedApproved = 0;
        for (int index = 0; index < 2; index++) {
            String id = "generated-" + index;
            route(id);
            String first = index == 0 ? "legal" : "security";
            String second = index == 0 ? "security" : "legal";
            assertEquals("PENDING", decide(id, "d-first", "generated-a-" + index, first, "APPROVE"));
            assertEquals("PENDING", decide(id, "d-second", "generated-b-" + index, second, "APPROVE"));
            assertEquals("APPROVED", decide(id, "d-registrar", "generated-r-" + index, "registrar", "APPROVE"));
            generatedApproved++;
        }

        Files.createDirectories(Path.of("target"));
        Files.writeString(Path.of("target", "reference-approval-outcomes.json"),
                "{\"normal\":\"" + state("normal-route") + "\",\"reject\":\""
                        + state("reject-route") + "\",\"normal_decisions\":3,\"reject_decisions\":1,"
                        + "\"generated_approved\":" + generatedApproved + "}");
    }

    private void route(String id) {
        commands.createRoute(new EventEnvelope("j03.document.version-submitted", 1,
                        id + "-in", "document-service", AggregateType.DOCUMENT, id + "-doc", 1,
                        id + "-op", null, null),
                new VersionSubmitted(id + "-doc", id + "-version"), id + "-route",
                id + "-legacy-actor", id + "-out");
    }

    private String decide(String id, String decisionId, String actor, String role, String action) {
        return commands.decide(id + "-op-" + decisionId, id + "-event-" + decisionId,
                id + "-route", id + "-doc", id + "-version", decisionId, actor, role, action).state();
    }

    private String state(String routeId) throws SQLException {
        try (Connection connection = dataSource.getConnection(); PreparedStatement statement = connection.prepareStatement(
                "SELECT state FROM route WHERE route_id=?")) {
            statement.setString(1, routeId);
            try (ResultSet row = statement.executeQuery()) { row.next(); return row.getString(1); }
        }
    }

    private long count(String predicate) throws SQLException {
        try (Connection connection = dataSource.getConnection(); Statement statement = connection.createStatement();
             ResultSet row = statement.executeQuery("SELECT count(*) FROM " + predicate)) {
            row.next(); return row.getLong(1);
        }
    }
}
