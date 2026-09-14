package dev.deltafuse.bench.workflow;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import dev.deltafuse.bench.contracts.AggregateType;
import dev.deltafuse.bench.contracts.ErrorCode;
import dev.deltafuse.bench.contracts.EventEnvelope;
import dev.deltafuse.bench.contracts.VersionSubmitted;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.postgresql.ds.PGSimpleDataSource;
import org.testcontainers.containers.PostgreSQLContainer;

@Tag("db-integration")
class WorkflowCommandServiceTest {
    private static PostgreSQLContainer<?> postgres;
    private static PGSimpleDataSource dataSource;
    private WorkflowCommandService commands;

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
        if (postgres != null) postgres.stop();
    }

    @BeforeEach
    void resetDatabase() throws SQLException {
        try (Connection connection = dataSource.getConnection(); Statement statement = connection.createStatement()) {
            statement.execute("TRUNCATE decision_receipt, route_receipt, decision, outbox_event, inbox_event, route CASCADE");
        }
        commands = new WorkflowCommandService(dataSource);
    }

    @Test
    void submission_atomically_creates_inbox_route_and_outbox() throws SQLException {
        RouteResult result = createRoute("in-1", "doc-1", "ver-1", "route-1", "actor-1", "out-1");
        assertEquals(new RouteResult("route-1", "doc-1", "ver-1", "actor-1", "PENDING", "out-1", 1), result);
        assertEquals(1, count("inbox_event"));
        assertEquals(1, count("route"));
        assertEquals(1, count("outbox_event"));
        assertEquals("j03.workflow.route-created", scalar("SELECT schema_name FROM outbox_event"));
    }

    @Test
    void duplicate_delivery_returns_prior_route_without_repeated_effect() throws SQLException {
        RouteResult first = createRoute("in-2", "doc-2", "ver-2", "route-2", "actor-2", "out-2");
        RouteResult replay = createRoute("in-2", "doc-2", "ver-2", "route-2", "actor-2", "out-2");
        assertEquals(first, replay);
        assertEquals(1, count("inbox_event"));
        assertEquals(1, count("route"));
        assertEquals(1, count("outbox_event"));
        WorkflowFailure conflict = assertThrows(WorkflowFailure.class,
                () -> createRoute("in-2", "doc-other", "ver-2", "route-2", "actor-2", "out-2"));
        assertEquals(ErrorCode.IDEMPOTENCY_CONFLICT, conflict.code());
    }

    @Test
    void approve_and_reject_close_routes_with_derived_state() throws SQLException {
        createRoute("in-3a", "doc-3a", "ver-3a", "route-3a", "actor-3a", "out-3a");
        DecisionResult approved = commands.decide(
                "op-3a", "evt-3a", "route-3a", "doc-3a", "ver-3a", "dec-3a", "actor-3a", "approver", "APPROVE");
        assertEquals("APPROVED", approved.state());
        createRoute("in-3b", "doc-3b", "ver-3b", "route-3b", "actor-3b", "out-3b");
        DecisionResult rejected = commands.decide(
                "op-3b", "evt-3b", "route-3b", "doc-3b", "ver-3b", "dec-3b", "actor-3b", "approver", "REJECT");
        assertEquals("REJECTED", rejected.state());
        assertEquals(2, count("decision"));
        assertEquals(4, count("outbox_event"));
    }

    @Test
    void exact_decision_replay_is_stable_but_changed_payload_conflicts() throws SQLException {
        createRoute("in-4", "doc-4", "ver-4", "route-4", "actor-4", "out-4");
        DecisionResult first = commands.decide(
                "op-4", "evt-4", "route-4", "doc-4", "ver-4", "dec-4", "actor-4", "approver", "APPROVE");
        DecisionResult replay = commands.decide(
                "op-4", "evt-4", "route-4", "doc-4", "ver-4", "dec-4", "actor-4", "approver", "APPROVE");
        assertEquals(first, replay);
        WorkflowFailure conflict = assertThrows(WorkflowFailure.class,
                () -> commands.decide("op-4b", "evt-4b", "route-4", "doc-4", "ver-4",
                        "dec-4", "actor-4", "approver", "REJECT"));
        assertEquals(ErrorCode.IDEMPOTENCY_CONFLICT, conflict.code());
        assertEquals(1, count("decision"));
        assertEquals(2, count("outbox_event"));
    }

    @Test
    void wrong_identity_or_actor_has_no_decision_or_outbox_effect() throws SQLException {
        createRoute("in-5", "doc-5", "ver-5", "route-5", "actor-5", "out-5");
        for (Runnable attempt : new Runnable[] {
                () -> commands.decide("op-5a", "evt-5a", "route-5", "doc-5", "wrong", "dec-5a", "actor-5", "approver", "APPROVE"),
                () -> commands.decide("op-5b", "evt-5b", "route-5", "doc-5", "ver-5", "dec-5b", "other", "approver", "APPROVE")}) {
            WorkflowFailure failure = assertThrows(WorkflowFailure.class, attempt::run);
            assertEquals(ErrorCode.IDENTITY_MISMATCH, failure.code());
        }
        assertEquals(0, count("decision"));
        assertEquals(1, count("outbox_event"));
        assertEquals("PENDING", scalar("SELECT state FROM route WHERE route_id='route-5'"));
    }

    @Test
    void target_roles_actions_and_second_transition_are_absent() throws SQLException {
        createRoute("in-6", "doc-6", "ver-6", "route-6", "actor-6", "out-6");
        assertEquals(ErrorCode.INVALID_SCHEMA, assertThrows(WorkflowFailure.class,
                () -> commands.decide("op-6a", "evt-6a", "route-6", "doc-6", "ver-6",
                        "dec-6a", "actor-6", "registrar", "APPROVE")).code());
        assertEquals(ErrorCode.UNSUPPORTED_ACTION, assertThrows(WorkflowFailure.class,
                () -> commands.decide("op-6b", "evt-6b", "route-6", "doc-6", "ver-6",
                        "dec-6b", "actor-6", "approver", "ESCALATE")).code());
        commands.decide("op-6c", "evt-6c", "route-6", "doc-6", "ver-6",
                "dec-6c", "actor-6", "approver", "APPROVE");
        assertEquals(ErrorCode.IDENTITY_MISMATCH, assertThrows(WorkflowFailure.class,
                () -> commands.decide("op-6d", "evt-6d", "route-6", "doc-6", "ver-6",
                        "dec-6d", "actor-6", "approver", "APPROVE")).code());
    }

    @Test
    void forced_failure_rolls_back_decision_state_receipt_and_outbox() throws SQLException {
        createRoute("in-7", "doc-7", "ver-7", "route-7", "actor-7", "out-7");
        WorkflowCommandService failing = new WorkflowCommandService(dataSource,
                connection -> { throw new IllegalStateException("forced-before-commit"); });
        assertThrows(IllegalStateException.class,
                () -> failing.decide("op-7", "evt-7", "route-7", "doc-7", "ver-7",
                        "dec-7", "actor-7", "approver", "APPROVE"));
        assertEquals("PENDING", scalar("SELECT state FROM route WHERE route_id='route-7'"));
        assertEquals(0, count("decision"));
        assertEquals(0, count("decision_receipt"));
        assertEquals(1, count("outbox_event"));
    }

    @Test
    void forced_failure_rolls_back_input_receipt_route_and_output() throws SQLException {
        WorkflowCommandService failing = new WorkflowCommandService(dataSource,
                connection -> { throw new IllegalStateException("forced-before-commit"); });
        EventEnvelope envelope = new EventEnvelope("j03.document.version-submitted", 1, "in-7b",
                "document-service", AggregateType.DOCUMENT, "doc-7b", 3, "in-7b", null, null);
        assertThrows(IllegalStateException.class,
                () -> failing.createRoute(envelope, new VersionSubmitted("doc-7b", "ver-7b"),
                        "route-7b", "actor-7b", "out-7b"));
        assertEquals(0, count("inbox_event"));
        assertEquals(0, count("route"));
        assertEquals(0, count("route_receipt"));
        assertEquals(0, count("outbox_event"));
    }

    @Test
    void unknown_submission_schema_rejects_before_inbox_write() throws SQLException {
        EventEnvelope envelope = new EventEnvelope("j03.document.created", 1, "in-7c",
                "document-service", AggregateType.DOCUMENT, "doc-7c", 1, "in-7c", null, null);
        WorkflowFailure failure = assertThrows(WorkflowFailure.class,
                () -> commands.createRoute(envelope, new VersionSubmitted("doc-7c", "ver-7c"),
                        "route-7c", "actor-7c", "out-7c"));
        assertEquals(ErrorCode.INVALID_SCHEMA, failure.code());
        assertEquals(0, count("inbox_event"));
    }

    @Test
    void per_document_database_lock_allows_only_one_pending_route() throws Exception {
        CompletableFuture<RouteResult> first = CompletableFuture.supplyAsync(
                () -> createRoute("in-8a", "doc-8", "ver-8a", "route-8a", "actor-8", "out-8a"));
        CompletableFuture<RouteResult> second = CompletableFuture.supplyAsync(
                () -> createRoute("in-8b", "doc-8", "ver-8b", "route-8b", "actor-8", "out-8b"));
        int successes = 0;
        int identityFailures = 0;
        for (CompletableFuture<RouteResult> future : new CompletableFuture[] {first, second}) {
            try {
                future.join();
                successes++;
            } catch (CompletionException failure) {
                assertTrue(failure.getCause() instanceof WorkflowFailure);
                assertEquals(ErrorCode.IDENTITY_MISMATCH, ((WorkflowFailure) failure.getCause()).code());
                identityFailures++;
            }
        }
        assertEquals(1, successes);
        assertEquals(1, identityFailures);
        assertEquals(1, count("route"));
        assertEquals(1, count("inbox_event"));
    }

    private RouteResult createRoute(String inputEventId, String documentId, String versionId,
            String routeId, String actorId, String outputEventId) {
        EventEnvelope envelope = new EventEnvelope("j03.document.version-submitted", 1, inputEventId,
                "document-service", AggregateType.DOCUMENT, documentId, 3, inputEventId, null, null);
        return commands.createRoute(envelope, new VersionSubmitted(documentId, versionId),
                routeId, actorId, outputEventId);
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
