package dev.deltafuse.bench.document;

import dev.deltafuse.bench.contracts.AggregateType;
import dev.deltafuse.bench.contracts.CanonicalJson;
import dev.deltafuse.bench.contracts.ContractViolation;
import dev.deltafuse.bench.contracts.DocumentCreated;
import dev.deltafuse.bench.contracts.ErrorCode;
import dev.deltafuse.bench.contracts.EventEnvelope;
import dev.deltafuse.bench.contracts.Idempotency;
import dev.deltafuse.bench.contracts.JsonObj;
import dev.deltafuse.bench.contracts.JsonStr;
import dev.deltafuse.bench.contracts.Payload;
import dev.deltafuse.bench.contracts.VersionCreated;
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

/** Transactional baseline commands for the document aggregate. */
@Service
public final class DocumentCommandService {
    private static final String PRODUCER = "document-service";

    private final DataSource dataSource;
    private final BeforeCommitHook beforeCommit;

    @Autowired
    public DocumentCommandService(DataSource dataSource) {
        this(dataSource, connection -> { });
    }

    DocumentCommandService(DataSource dataSource, BeforeCommitHook beforeCommit) {
        this.dataSource = dataSource;
        this.beforeCommit = beforeCommit;
    }

    public CommandResult createDocument(
            String operationId, String eventId, String documentId, String title) {
        DocumentCreated payload = validate(operationId, () -> new DocumentCreated(documentId, title));
        String request = requestJson("CREATE_DOCUMENT", eventId, payload.toJson());
        return inTransaction(connection -> {
            CommandResult replay = replay(connection, operationId, "CREATE_DOCUMENT", request);
            if (replay != null) {
                return replay;
            }
            validateEnvelope(operationId, eventId, documentId, 1, "j03.document.created");
            update(connection, "INSERT INTO document (document_id, title) VALUES (?, ?)", documentId, title);
            insertOutbox(connection, eventId, documentId, 1, "j03.document.created", payload);
            CommandResult result = new CommandResult(operationId, documentId, null, "DRAFT", eventId, 1);
            insertReceipt(connection, "CREATE_DOCUMENT", request, result);
            return result;
        });
    }

    public CommandResult createVersion(
            String operationId, String eventId, String documentId, String versionId, String content) {
        VersionCreated payload = validate(operationId, () -> new VersionCreated(documentId, versionId, content));
        String request = requestJson("CREATE_VERSION", eventId, payload.toJson());
        return inTransaction(connection -> {
            CommandResult replay = replay(connection, operationId, "CREATE_VERSION", request);
            if (replay != null) {
                return replay;
            }
            requireDocument(connection, operationId, documentId);
            long sequence = nextSequence(connection, documentId);
            validateEnvelope(operationId, eventId, documentId, sequence, "j03.document.version-created");
            update(connection, "INSERT INTO document_version (document_id, version_id, content, state) "
                    + "VALUES (?, ?, ?, 'DRAFT')", documentId, versionId, content);
            insertOutbox(connection, eventId, documentId, sequence, "j03.document.version-created", payload);
            CommandResult result = new CommandResult(operationId, documentId, versionId, "DRAFT", eventId, sequence);
            insertReceipt(connection, "CREATE_VERSION", request, result);
            return result;
        });
    }

    public CommandResult submitVersion(
            String operationId, String eventId, String documentId, String versionId) {
        VersionSubmitted payload = validate(operationId, () -> new VersionSubmitted(documentId, versionId));
        String request = requestJson("SUBMIT_VERSION", eventId, payload.toJson());
        return inTransaction(connection -> {
            CommandResult replay = replay(connection, operationId, "SUBMIT_VERSION", request);
            if (replay != null) {
                return replay;
            }
            requireDocument(connection, operationId, documentId);
            String state = versionState(connection, operationId, documentId, versionId);
            if (!"DRAFT".equals(state)) {
                throw new DocumentFailure(ErrorCode.VERSION_IMMUTABLE, operationId, "version is already immutable");
            }
            long sequence = nextSequence(connection, documentId);
            validateEnvelope(operationId, eventId, documentId, sequence, "j03.document.version-submitted");
            update(connection, "UPDATE document_version SET state='SUBMITTED' "
                    + "WHERE document_id=? AND version_id=?", documentId, versionId);
            insertOutbox(connection, eventId, documentId, sequence, "j03.document.version-submitted", payload);
            CommandResult result = new CommandResult(
                    operationId, documentId, versionId, "SUBMITTED", eventId, sequence);
            insertReceipt(connection, "SUBMIT_VERSION", request, result);
            return result;
        });
    }

    private CommandResult replay(Connection connection, String operationId, String commandType, String request)
            throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                "SELECT command_type, request_payload::text, result_document_id, result_version_id, "
                        + "result_state, result_event_id, result_domain_sequence "
                        + "FROM command_receipt WHERE operation_id=?")) {
            statement.setString(1, operationId);
            try (ResultSet row = statement.executeQuery()) {
                if (!row.next()) {
                    return null;
                }
                if (!commandType.equals(row.getString(1))) {
                    throw new DocumentFailure(ErrorCode.IDEMPOTENCY_CONFLICT, operationId,
                            "operation key belongs to another command");
                }
                try {
                    Idempotency.requireSamePayload(operationId, row.getString(2), request);
                } catch (ContractViolation violation) {
                    throw new DocumentFailure(violation.code(), operationId, violation.getMessage());
                }
                return new CommandResult(operationId, row.getString(3), row.getString(4), row.getString(5),
                        row.getString(6), row.getLong(7));
            }
        }
    }

    private void requireDocument(Connection connection, String operationId, String documentId) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                "SELECT document_id FROM document WHERE document_id=? FOR UPDATE")) {
            statement.setString(1, documentId);
            try (ResultSet row = statement.executeQuery()) {
                if (!row.next()) {
                    throw new DocumentFailure(ErrorCode.DOCUMENT_NOT_FOUND, operationId, "document not found");
                }
            }
        }
    }

    private String versionState(Connection connection, String operationId, String documentId, String versionId)
            throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                "SELECT state FROM document_version WHERE document_id=? AND version_id=? FOR UPDATE")) {
            statement.setString(1, documentId);
            statement.setString(2, versionId);
            try (ResultSet row = statement.executeQuery()) {
                if (!row.next()) {
                    throw new DocumentFailure(ErrorCode.VERSION_NOT_FOUND, operationId, "version not found");
                }
                return row.getString(1);
            }
        }
    }

    private long nextSequence(Connection connection, String documentId) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                "SELECT COALESCE(MAX(domain_sequence), 0) + 1 FROM outbox_event "
                        + "WHERE aggregate_type='DOCUMENT' AND aggregate_id=?")) {
            statement.setString(1, documentId);
            try (ResultSet row = statement.executeQuery()) {
                row.next();
                return row.getLong(1);
            }
        }
    }

    private void insertOutbox(Connection connection, String eventId, String documentId, long sequence,
            String schemaName, Payload payload) throws SQLException {
        update(connection, "INSERT INTO outbox_event (event_id, aggregate_type, aggregate_id, domain_sequence, "
                        + "schema_name, schema_version, payload) VALUES (?, 'DOCUMENT', ?, ?, ?, 1, ?::jsonb)",
                eventId, documentId, sequence, schemaName, CanonicalJson.write(payload.toJson()));
    }

    private void insertReceipt(Connection connection, String commandType, String request, CommandResult result)
            throws SQLException {
        update(connection, "INSERT INTO command_receipt (operation_id, command_type, request_payload, "
                        + "result_document_id, result_version_id, result_state, result_event_id, "
                        + "result_domain_sequence) VALUES (?, ?, ?::jsonb, ?, ?, ?, ?, ?)",
                result.operationId(), commandType, request, result.documentId(), result.versionId(), result.state(),
                result.eventId(), result.domainSequence());
    }

    private static String requestJson(String command, String eventId, JsonObj payload) {
        Map<String, dev.deltafuse.bench.contracts.JsonValue> members = new LinkedHashMap<>(payload.members());
        members.put("command", new JsonStr(command));
        members.put("event_id", new JsonStr(eventId));
        return CanonicalJson.write(JsonObj.of(members));
    }

    private static void validateEnvelope(
            String operationId, String eventId, String documentId, long sequence, String schemaName) {
        validate(operationId, () -> new EventEnvelope(schemaName, 1, eventId, PRODUCER, AggregateType.DOCUMENT,
                documentId, sequence, operationId, null, null));
    }

    private static <T> T validate(String operationId, Factory<T> factory) {
        try {
            return factory.create();
        } catch (ContractViolation | IllegalArgumentException violation) {
            ErrorCode code = violation instanceof ContractViolation contract
                    ? contract.code() : ErrorCode.INVALID_SCHEMA;
            throw new DocumentFailure(code, operationId, violation.getMessage());
        }
    }

    private CommandResult inTransaction(SqlWork work) {
        try (Connection connection = dataSource.getConnection()) {
            connection.setAutoCommit(false);
            try {
                CommandResult result = work.run(connection);
                beforeCommit.run(connection);
                connection.commit();
                return result;
            } catch (RuntimeException | SQLException failure) {
                try {
                    connection.rollback();
                } catch (SQLException rollbackFailure) {
                    failure.addSuppressed(rollbackFailure);
                }
                if (failure instanceof RuntimeException runtime) {
                    throw runtime;
                }
                throw new IllegalStateException("document transaction failed", failure);
            }
        } catch (SQLException failure) {
            throw new IllegalStateException("document database unavailable", failure);
        }
    }

    private static void update(Connection connection, String sql, Object... values) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            for (int index = 0; index < values.length; index++) {
                statement.setObject(index + 1, values[index]);
            }
            statement.executeUpdate();
        }
    }

    @FunctionalInterface
    interface BeforeCommitHook {
        void run(Connection connection) throws SQLException;
    }

    @FunctionalInterface
    private interface SqlWork {
        CommandResult run(Connection connection) throws SQLException;
    }

    @FunctionalInterface
    private interface Factory<T> {
        T create();
    }
}
