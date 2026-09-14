package dev.deltafuse.bench.workflow;

import dev.deltafuse.bench.contracts.ActorRole;
import dev.deltafuse.bench.contracts.AggregateType;
import dev.deltafuse.bench.contracts.BaselineEvents;
import dev.deltafuse.bench.contracts.CanonicalJson;
import dev.deltafuse.bench.contracts.ContractViolation;
import dev.deltafuse.bench.contracts.DecisionAction;
import dev.deltafuse.bench.contracts.DecisionApplied;
import dev.deltafuse.bench.contracts.ErrorCode;
import dev.deltafuse.bench.contracts.EventEnvelope;
import dev.deltafuse.bench.contracts.Idempotency;
import dev.deltafuse.bench.contracts.JsonObj;
import dev.deltafuse.bench.contracts.JsonStr;
import dev.deltafuse.bench.contracts.JsonValue;
import dev.deltafuse.bench.contracts.Payload;
import dev.deltafuse.bench.contracts.RouteCreated;
import dev.deltafuse.bench.contracts.VersionSubmitted;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.LinkedHashMap;
import java.util.Map;
import javax.sql.DataSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public final class WorkflowCommandService {
    private static final String PRODUCER = "workflow-service";
    private final DataSource dataSource;
    private final BeforeCommitHook beforeCommit;

    @Autowired
    public WorkflowCommandService(DataSource dataSource) {
        this(dataSource, connection -> { });
    }

    WorkflowCommandService(DataSource dataSource, BeforeCommitHook beforeCommit) {
        this.dataSource = dataSource;
        this.beforeCommit = beforeCommit;
    }

    public RouteResult createRoute(EventEnvelope input, VersionSubmitted submission,
            String routeId, String approverActorId, String outputEventId) {
        String operationId = input.eventId();
        validateSubmission(operationId, input, submission);
        RouteCreated output = validate(operationId,
                () -> new RouteCreated(submission.documentId(), submission.versionId(), routeId, approverActorId));
        validateEnvelope(operationId, outputEventId, AggregateType.ROUTE, routeId, 1,
                "j03.workflow.route-created", input.eventId());
        String request = routeRequest(input, submission, routeId, approverActorId, outputEventId);
        return transaction(connection -> {
            RouteResult replay = routeReplay(connection, input.eventId(), request);
            if (replay != null) return replay;
            lockDocument(connection, submission.documentId());
            replay = routeReplay(connection, input.eventId(), request);
            if (replay != null) return replay;
            if (hasPendingRoute(connection, submission.documentId())) {
                throw new WorkflowFailure(ErrorCode.IDENTITY_MISMATCH, operationId,
                        "baseline document already has a pending route");
            }
            update(connection, "INSERT INTO inbox_event (event_id) VALUES (?)", input.eventId());
            update(connection, "INSERT INTO route (route_id, document_id, version_id, approver_actor_id, state) "
                    + "VALUES (?, ?, ?, ?, 'PENDING')", routeId, submission.documentId(),
                    submission.versionId(), approverActorId);
            insertOutbox(connection, outputEventId, routeId, 1, "j03.workflow.route-created", output);
            RouteResult result = new RouteResult(routeId, submission.documentId(), submission.versionId(),
                    approverActorId, "PENDING", outputEventId, 1);
            update(connection, "INSERT INTO route_receipt (input_event_id, request_payload, result_route_id, "
                            + "result_document_id, result_version_id, result_approver_actor_id, result_event_id, "
                            + "result_domain_sequence) VALUES (?, ?::jsonb, ?, ?, ?, ?, ?, 1)",
                    input.eventId(), request, routeId, submission.documentId(), submission.versionId(),
                    approverActorId, outputEventId);
            return result;
        });
    }

    public DecisionResult decide(String operationId, String eventId, String routeId, String documentId,
            String versionId, String decisionId, String actorId, String roleValue, String actionValue) {
        ActorRole role = validate(operationId, () -> ActorRole.parse(roleValue));
        DecisionAction action = validate(operationId, () -> DecisionAction.parse(actionValue));
        DecisionApplied decision = validate(operationId,
                () -> new DecisionApplied(documentId, versionId, routeId, decisionId, actorId, role, action));
        validateEnvelope(operationId, eventId, AggregateType.ROUTE, routeId, 2,
                "j03.workflow.decision-applied", null);
        String request = decisionRequest(operationId, eventId, decision);
        return transaction(connection -> {
            DecisionResult replay = decisionReplay(connection, operationId, routeId, decisionId, request);
            if (replay != null) return replay;
            RouteRow route = lockRoute(connection, operationId, routeId);
            replay = decisionReplay(connection, operationId, routeId, decisionId, request);
            if (replay != null) return replay;
            if (!route.documentId().equals(documentId) || !route.versionId().equals(versionId)
                    || !route.approverActorId().equals(actorId)) {
                throw new WorkflowFailure(ErrorCode.IDENTITY_MISMATCH, operationId,
                        "route, version, document or actor identity mismatch");
            }
            if (!"PENDING".equals(route.state())) {
                throw new WorkflowFailure(ErrorCode.IDENTITY_MISMATCH, operationId, "route is already closed");
            }
            String state = decision.resultingState().name();
            update(connection, "INSERT INTO decision (route_id, decision_id, actor_id, role, action, "
                            + "resulting_state) VALUES (?, ?, ?, 'approver', ?, ?)",
                    routeId, decisionId, actorId, action.name(), state);
            update(connection, "UPDATE route SET state=? WHERE route_id=?", state, routeId);
            insertOutbox(connection, eventId, routeId, 2, "j03.workflow.decision-applied", decision);
            update(connection, "INSERT INTO decision_receipt (route_id, decision_id, operation_id, "
                            + "request_payload, result_event_id, result_state, result_domain_sequence) "
                            + "VALUES (?, ?, ?, ?::jsonb, ?, ?, 2)",
                    routeId, decisionId, operationId, request, eventId, state);
            return new DecisionResult(operationId, routeId, decisionId, state, eventId, 2);
        });
    }

    private RouteResult routeReplay(Connection connection, String inputEventId, String request) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                "SELECT request_payload::text, result_route_id, result_document_id, result_version_id, "
                        + "result_approver_actor_id, result_event_id, result_domain_sequence "
                        + "FROM route_receipt WHERE input_event_id=?")) {
            statement.setString(1, inputEventId);
            try (ResultSet row = statement.executeQuery()) {
                if (!row.next()) return null;
                requireSame(inputEventId, row.getString(1), request);
                return new RouteResult(row.getString(2), row.getString(3), row.getString(4), row.getString(5),
                        "PENDING", row.getString(6), row.getLong(7));
            }
        }
    }

    private DecisionResult decisionReplay(Connection connection, String operationId, String routeId,
            String decisionId, String request) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                "SELECT operation_id, request_payload::text, result_event_id, result_state, result_domain_sequence "
                        + "FROM decision_receipt WHERE route_id=? AND decision_id=?")) {
            statement.setString(1, routeId);
            statement.setString(2, decisionId);
            try (ResultSet row = statement.executeQuery()) {
                if (!row.next()) return null;
                // DEC-D: decision_id is the domain idempotency key of the
                // route. The binding comparison ignores operation and event
                // identities so a repeated decision under a new operation
                // returns the prior result instead of conflicting.
                requireSameDecisionBinding(operationId, row.getString(2), request);
                return new DecisionResult(operationId, routeId, decisionId, row.getString(4),
                        row.getString(3), row.getLong(5));
            }
        }
    }

    private static void requireSameDecisionBinding(String operationId, String stored, String incoming) {
        if (!sameDecisionBinding(stored, incoming)) {
            throw new WorkflowFailure(ErrorCode.IDEMPOTENCY_CONFLICT, operationId,
                    "decision id replayed with a different payload");
        }
    }

    private static boolean sameDecisionBinding(String stored, String incoming) {
        try {
            JsonObj a = withoutAttemptIdentity(CanonicalJson.parse(stored).asObj());
            JsonObj b = withoutAttemptIdentity(CanonicalJson.parse(incoming).asObj());
            return a.equals(b);
        } catch (IllegalArgumentException failure) {
            return false;
        }
    }

    private static JsonObj withoutAttemptIdentity(JsonObj obj) {
        Map<String, JsonValue> members = new LinkedHashMap<>(obj.members());
        members.remove("operation_id");
        members.remove("event_id");
        return JsonObj.of(members);
    }

    private static void requireSame(String operationId, String stored, String incoming) {
        try {
            Idempotency.requireSamePayload(operationId, stored, incoming);
        } catch (ContractViolation failure) {
            throw new WorkflowFailure(failure.code(), operationId, failure.getMessage());
        }
    }

    private static RouteRow lockRoute(Connection connection, String operationId, String routeId) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                "SELECT document_id, version_id, approver_actor_id, state FROM route WHERE route_id=? FOR UPDATE")) {
            statement.setString(1, routeId);
            try (ResultSet row = statement.executeQuery()) {
                if (!row.next()) throw new WorkflowFailure(ErrorCode.IDENTITY_MISMATCH, operationId, "route not found");
                return new RouteRow(row.getString(1), row.getString(2), row.getString(3), row.getString(4));
            }
        }
    }

    private static void lockDocument(Connection connection, String documentId) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                "SELECT pg_advisory_xact_lock(hashtextextended(?, 0))")) {
            statement.setString(1, documentId);
            statement.executeQuery().close();
        }
    }

    private static boolean hasPendingRoute(Connection connection, String documentId) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                "SELECT 1 FROM route WHERE document_id=? AND state='PENDING'")) {
            statement.setString(1, documentId);
            try (ResultSet row = statement.executeQuery()) { return row.next(); }
        }
    }

    private static void insertOutbox(Connection connection, String eventId, String routeId, long sequence,
            String schemaName, Payload payload) throws SQLException {
        update(connection, "INSERT INTO outbox_event (event_id, aggregate_type, aggregate_id, domain_sequence, "
                        + "schema_name, schema_version, payload) VALUES (?, 'ROUTE', ?, ?, ?, 1, ?::jsonb)",
                eventId, routeId, sequence, schemaName, CanonicalJson.write(payload.toJson()));
    }

    private static String routeRequest(EventEnvelope input, VersionSubmitted submission,
            String routeId, String actorId, String outputEventId) {
        Map<String, JsonValue> members = new LinkedHashMap<>();
        members.put("input_event", CanonicalJson.parse(BaselineEvents.encode(input, submission.toJson())));
        members.put("route_id", new JsonStr(routeId));
        members.put("approver_actor_id", new JsonStr(actorId));
        members.put("output_event_id", new JsonStr(outputEventId));
        return CanonicalJson.write(JsonObj.of(members));
    }

    private static String decisionRequest(String operationId, String eventId, DecisionApplied decision) {
        Map<String, JsonValue> members = new LinkedHashMap<>(decision.toJson().members());
        members.put("operation_id", new JsonStr(operationId));
        members.put("event_id", new JsonStr(eventId));
        return CanonicalJson.write(JsonObj.of(members));
    }

    private static void validateSubmission(String operationId, EventEnvelope input, VersionSubmitted submission) {
        if (!"j03.document.version-submitted".equals(input.schemaName()) || input.schemaVersion() != 1) {
            throw new WorkflowFailure(ErrorCode.INVALID_SCHEMA, operationId, "unknown submission schema");
        }
        if (!"document-service".equals(input.producer()) || input.aggregateType() != AggregateType.DOCUMENT
                || !input.aggregateId().equals(submission.documentId())) {
            throw new WorkflowFailure(ErrorCode.IDENTITY_MISMATCH, operationId,
                    "submission envelope identity mismatch");
        }
    }

    private static void validateEnvelope(String operationId, String eventId, AggregateType aggregateType,
            String aggregateId, long sequence, String schemaName, String causationId) {
        validate(operationId, () -> new EventEnvelope(schemaName, 1, eventId, PRODUCER, aggregateType,
                aggregateId, sequence, operationId, causationId, null));
    }

    private <T> T transaction(SqlWork<T> work) {
        try (Connection connection = dataSource.getConnection()) {
            connection.setAutoCommit(false);
            try {
                T result = work.run(connection);
                beforeCommit.run(connection);
                connection.commit();
                return result;
            } catch (RuntimeException | SQLException failure) {
                try { connection.rollback(); } catch (SQLException rollback) { failure.addSuppressed(rollback); }
                if (failure instanceof RuntimeException runtime) throw runtime;
                throw new IllegalStateException("workflow transaction failed", failure);
            }
        } catch (SQLException failure) {
            throw new IllegalStateException("workflow database unavailable", failure);
        }
    }

    private static <T> T validate(String operationId, Factory<T> factory) {
        try {
            return factory.create();
        } catch (ContractViolation | IllegalArgumentException failure) {
            ErrorCode code = failure instanceof ContractViolation contract
                    ? contract.code() : ErrorCode.INVALID_SCHEMA;
            throw new WorkflowFailure(code, operationId, failure.getMessage());
        }
    }

    private static void update(Connection connection, String sql, Object... values) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            for (int i = 0; i < values.length; i++) statement.setObject(i + 1, values[i]);
            statement.executeUpdate();
        }
    }

    private record RouteRow(String documentId, String versionId, String approverActorId, String state) { }
    @FunctionalInterface interface BeforeCommitHook { void run(Connection connection) throws SQLException; }
    @FunctionalInterface private interface SqlWork<T> { T run(Connection connection) throws SQLException; }
    @FunctionalInterface private interface Factory<T> { T create(); }
}
