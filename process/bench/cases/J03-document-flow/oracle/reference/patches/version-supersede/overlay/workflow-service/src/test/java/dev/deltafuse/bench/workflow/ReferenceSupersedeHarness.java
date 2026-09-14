package dev.deltafuse.bench.workflow;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import dev.deltafuse.bench.contracts.AggregateType;
import dev.deltafuse.bench.contracts.CanonicalJson;
import dev.deltafuse.bench.contracts.EventEnvelope;
import dev.deltafuse.bench.contracts.JsonArr;
import dev.deltafuse.bench.contracts.JsonBool;
import dev.deltafuse.bench.contracts.JsonNull;
import dev.deltafuse.bench.contracts.JsonNum;
import dev.deltafuse.bench.contracts.JsonObj;
import dev.deltafuse.bench.contracts.JsonStr;
import dev.deltafuse.bench.contracts.JsonValue;
import dev.deltafuse.bench.contracts.VersionSubmitted;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.postgresql.ds.PGSimpleDataSource;
import org.testcontainers.containers.PostgreSQLContainer;

/**
 * Private reference harness (judge overlay, J03-303): executes the
 * version-supersede scenarios on the patched reference with real
 * PostgreSQL, asserts the reference invariants, and writes both the
 * observed outcomes and the mirrored operation stream as canonical JSON for
 * the independent interpreter comparison in
 * {@code tests/bench/document_flow/test_reference_supersede.py}.
 */
@Tag("db-integration")
class ReferenceSupersedeHarness {

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
        try (Connection connection = dataSource.getConnection();
             Statement statement = connection.createStatement()) {
            statement.execute("TRUNCATE decision_receipt, route_receipt, decision, "
                    + "outbox_event, inbox_event, route CASCADE");
        }
        commands = new WorkflowCommandService(dataSource);
    }

    @Test
    void supersede_scenarios_hold_and_match_the_recorded_operations() throws Exception {
        List<Map<String, Object>> reports = new ArrayList<>();
        reports.add(supersedeBeforeDecision());
        reports.add(supersedeAfterRedeliveryAndLateDecision());
        reports.add(crashDuringSupersedeIsAtomicAndRetried());
        List<JsonValue> entries = new ArrayList<>();
        for (Map<String, Object> report : reports) {
            entries.add(toJsonValue(report));
        }
        Files.createDirectories(Path.of("target"));
        Files.writeString(Path.of("target", "reference-supersede-outcomes.json"),
                CanonicalJson.write(JsonObj.of(Map.of("scenarios", new JsonArr(entries)))));
        assertTrue(Files.exists(Path.of("target", "reference-supersede-outcomes.json")));
    }

    // S1: supersede before any decision; the late decision on the old route
    // is ignored exactly once (its replay adds nothing); the successor closes.
    private Map<String, Object> supersedeBeforeDecision() throws Exception {
        List<Map<String, Object>> ops = new ArrayList<>();
        String doc = "S1-doc";
        recordCreate(ops, doc);
        recordVersion(ops, doc, "S1-ver-1");
        submit(ops, "S1", doc, "S1-ver-1", "S1-route-1", 3);
        recordVersion(ops, doc, "S1-ver-2");
        submit(ops, "S1", doc, "S1-ver-2", "S1-route-2", 6);
        decide(ops, "S1-route-1", doc, "S1-ver-1", "S1-dec-late", "S1-actor",
                "APPROVE");
        replayDecision(ops, "S1-route-1", doc, "S1-ver-1", "S1-dec-late",
                "S1-actor", "APPROVE");
        assertEquals("SUPERSEDED", state("S1-route-1"));
        assertEquals("PENDING", state("S1-route-2"));
        assertEquals(3, count("outbox_event WHERE aggregate_id='S1-route-1'"));
        return recordScenario("S1", ops);
    }

    // S2: duplicate delivery of the same submission is idempotent; the next
    // version supersedes; a late decision on the old route is ignored.
    private Map<String, Object> supersedeAfterRedeliveryAndLateDecision() throws Exception {
        List<Map<String, Object>> ops = new ArrayList<>();
        String doc = "S2-doc";
        recordCreate(ops, doc);
        recordVersion(ops, doc, "S2-ver-1");
        submit(ops, "S2", doc, "S2-ver-1", "S2-route-1", 3);
        ops.add(duplicateDelivery("S2-route-1-in", doc, "S2-ver-1"));
        commands.createRoute(envelope("S2-route-1-in", doc, 3),
                new VersionSubmitted(doc, "S2-ver-1"),
                "S2-route-1", "S2-actor", "S2-route-1-out");
        recordVersion(ops, doc, "S2-ver-2");
        submit(ops, "S2", doc, "S2-ver-2", "S2-route-2", 6);
        decide(ops, "S2-route-1", doc, "S2-ver-1", "S2-dec-late", "S2-actor",
                "APPROVE");
        assertEquals("SUPERSEDED", state("S2-route-1"));
        assertEquals("PENDING", state("S2-route-2"));
        assertEquals(3, count("outbox_event WHERE aggregate_id='S2-route-1'"));
        return recordScenario("S2", ops);
    }

    // S3: a forced crash during the supersede transaction leaves no partial
    // state; the retry completes exactly once.
    private Map<String, Object> crashDuringSupersedeIsAtomicAndRetried() throws Exception {
        List<Map<String, Object>> ops = new ArrayList<>();
        String doc = "S3-doc";
        recordCreate(ops, doc);
        recordVersion(ops, doc, "S3-ver-1");
        submit(ops, "S3", doc, "S3-ver-1", "S3-route-1", 3);
        WorkflowCommandService failing = new WorkflowCommandService(dataSource,
                connection -> { throw new IllegalStateException("forced-before-commit"); });
        try {
            failing.createRoute(envelope("S3-route-2-in", doc, 6),
                    new VersionSubmitted(doc, "S3-ver-2"),
                    "S3-route-2", "S3-actor", "S3-route-2-out");
            throw new AssertionError("forced failure did not fire");
        } catch (IllegalStateException expected) {
            // atomicity: nothing from the failed supersede survives
        }
        ops.add(Map.of("kind", "crash", "point", "after-commit-before-ack",
                "service", "workflow-service"));
        assertEquals("PENDING", state("S3-route-1"));
        assertEquals(0, count("route WHERE route_id='S3-route-2'"));
        assertEquals(1, count("outbox_event WHERE aggregate_id='S3-route-1'"));
        recordVersion(ops, doc, "S3-ver-2");
        submit(ops, "S3", doc, "S3-ver-2", "S3-route-2", 6);
        assertEquals("SUPERSEDED", state("S3-route-1"));
        assertEquals("PENDING", state("S3-route-2"));
        return recordScenario("S3", ops);
    }

    // ---- scenario plumbing -------------------------------------------------

    private void recordCreate(List<Map<String, Object>> ops, String documentId) {
        ops.add(new LinkedHashMap<>(Map.of("kind", "http", "op", "create-document",
                "document_id", documentId, "title", "Reference " + documentId)));
    }

    private void recordVersion(List<Map<String, Object>> ops, String documentId,
            String versionId) {
        ops.add(new LinkedHashMap<>(Map.of("kind", "http", "op", "create-version",
                "document_id", documentId, "version_id", versionId,
                "content", "Reference body " + versionId)));
    }

    private void submit(List<Map<String, Object>> ops, String scenario,
            String documentId, String versionId, String routeId, int inSequence)
            throws SQLException {
        ops.add(new LinkedHashMap<>(Map.of("kind", "http", "op", "submit-version",
                "document_id", documentId, "version_id", versionId)));
        commands.createRoute(envelope(routeId + "-in", documentId, inSequence),
                new VersionSubmitted(documentId, versionId),
                routeId, scenario + "-actor", routeId + "-out");
        ops.add(new LinkedHashMap<>(Map.of("kind", "delivery", "op", "route-created",
                "route_id", routeId, "document_id", documentId,
                "version_id", versionId, "event_id", routeId + "-out")));
        if (count("route WHERE document_id='" + documentId
                + "' AND state='SUPERSEDED'") > 0) {
            ops.add(new LinkedHashMap<>(Map.of("kind", "delivery",
                    "op", "route-superseded", "route_id", supersededRouteId(documentId),
                    "document_id", documentId, "version_id", supersededVersion(documentId),
                    "event_id", routeId + "-super")));
        }
    }

    private void decide(List<Map<String, Object>> ops, String routeId,
            String documentId, String versionId, String decisionId, String actor,
            String action) throws SQLException {
        String scenario = scenarioOf(decisionId);
        ops.add(new LinkedHashMap<>(Map.of("kind", "decision", "op", "decision",
                "route_id", routeId, "document_id", documentId,
                "version_id", versionId, "decision_id", decisionId,
                "actor_id", actor, "role", "legal", "action", action)));
        commands.decide(scenario + "-op-" + UUID.randomUUID(), scenario + "-evt-"
                        + UUID.randomUUID(), routeId, documentId, versionId,
                decisionId, actor, "approver", action);
    }

    private void replayDecision(List<Map<String, Object>> ops, String routeId,
            String documentId, String versionId, String decisionId, String actor,
            String action) throws SQLException {
        String scenario = scenarioOf(decisionId);
        ops.add(new LinkedHashMap<>(Map.of("kind", "duplicate-delivery",
                "op", "decision", "document_id", documentId,
                "version_id", versionId, "route_id", routeId,
                "decision_id", decisionId, "event_id", scenario + "-replay",
                "valid", true, "label", "duplicate-delivery")));
        commands.decide(scenario + "-replay-op", scenario + "-replay-event",
                routeId, documentId, versionId, decisionId, actor, "approver",
                action);
    }

    private Map<String, Object> duplicateDelivery(String eventId, String documentId,
            String versionId) {
        return new LinkedHashMap<>(Map.of("kind", "duplicate-delivery",
                "op", "submit-version", "document_id", documentId,
                "version_id", versionId, "event_id", eventId, "valid", true,
                "label", "duplicate-delivery"));
    }

    private String supersededRouteId(String documentId) throws SQLException {
        try (Connection connection = dataSource.getConnection();
             PreparedStatement statement = connection.prepareStatement(
                     "SELECT route_id FROM route WHERE document_id=? AND state='SUPERSEDED' "
                             + "ORDER BY created_at DESC LIMIT 1")) {
            statement.setString(1, documentId);
            try (ResultSet row = statement.executeQuery()) {
                row.next();
                return row.getString(1);
            }
        }
    }

    private String supersededVersion(String documentId) throws SQLException {
        try (Connection connection = dataSource.getConnection();
             PreparedStatement statement = connection.prepareStatement(
                     "SELECT version_id FROM route WHERE document_id=? AND state='SUPERSEDED' "
                             + "ORDER BY created_at DESC LIMIT 1")) {
            statement.setString(1, documentId);
            try (ResultSet row = statement.executeQuery()) {
                row.next();
                return row.getString(1);
            }
        }
    }

    private static String scenarioOf(String id) {
        return id.substring(0, id.indexOf('-'));
    }

    private Map<String, Object> recordScenario(String id,
            List<Map<String, Object>> operations) throws SQLException {
        Map<String, Object> routes = new LinkedHashMap<>();
        Map<String, Object> outboxByRoute = new LinkedHashMap<>();
        List<String> routeIds = new ArrayList<>();
        try (Connection connection = dataSource.getConnection();
             Statement statement = connection.createStatement();
             ResultSet rows = statement.executeQuery(
                     "SELECT route_id, version_id, state FROM route "
                             + "WHERE route_id LIKE '" + id + "-%' ORDER BY created_at, route_id")) {
            while (rows.next()) {
                String routeId = rows.getString(1);
                routeIds.add(routeId);
                Map<String, Object> route = new LinkedHashMap<>();
                route.put("version", rows.getString(2));
                route.put("state", rows.getString(3));
                routes.put(routeId, route);
            }
        }
        for (String routeId : routeIds) {
            List<String> kinds = new ArrayList<>();
            try (Connection connection = dataSource.getConnection();
                 PreparedStatement statement = connection.prepareStatement(
                         "SELECT schema_name FROM outbox_event WHERE aggregate_type='ROUTE' "
                                 + "AND aggregate_id=? ORDER BY domain_sequence, event_id")) {
                statement.setString(1, routeId);
                try (ResultSet rows = statement.executeQuery()) {
                    while (rows.next()) kinds.add(rows.getString(1));
                }
            }
            outboxByRoute.put(routeId, kinds);
        }
        Map<String, Object> report = new LinkedHashMap<>();
        report.put("id", id);
        report.put("operations", operations);
        report.put("routes", routes);
        report.put("outbox_by_route", outboxByRoute);
        return report;
    }

    private static EventEnvelope envelope(String eventId, String documentId, int sequence) {
        return new EventEnvelope("j03.document.version-submitted", 1, eventId,
                "document-service", AggregateType.DOCUMENT, documentId, sequence,
                eventId, null, null);
    }

    private String state(String routeId) throws SQLException {
        try (Connection connection = dataSource.getConnection();
             PreparedStatement statement = connection.prepareStatement(
                     "SELECT state FROM route WHERE route_id=?")) {
            statement.setString(1, routeId);
            try (ResultSet row = statement.executeQuery()) {
                if (!row.next()) throw new AssertionError("route absent: " + routeId);
                return row.getString(1);
            }
        }
    }

    private long count(String predicate) throws SQLException {
        try (Connection connection = dataSource.getConnection();
             Statement statement = connection.createStatement();
             ResultSet row = statement.executeQuery("SELECT count(*) FROM " + predicate)) {
            row.next();
            return row.getLong(1);
        }
    }

    private static JsonValue toJsonValue(Object value) {
        if (value == null) {
            return JsonNull.INSTANCE;
        }
        if (value instanceof String string) {
            return new JsonStr(string);
        }
        if (value instanceof Boolean bool) {
            return new JsonBool(bool);
        }
        if (value instanceof Integer integer) {
            return new JsonNum(integer);
        }
        if (value instanceof Long longValue) {
            return new JsonNum(longValue);
        }
        if (value instanceof List<?> list) {
            List<JsonValue> items = new ArrayList<>();
            for (Object item : list) {
                items.add(toJsonValue(item));
            }
            return new JsonArr(items);
        }
        if (value instanceof Map<?, ?> map) {
            Map<String, JsonValue> members = new LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                members.put(String.valueOf(entry.getKey()), toJsonValue(entry.getValue()));
            }
            return JsonObj.of(members);
        }
        throw new IllegalArgumentException("unsupported: " + value.getClass());
    }
}
