package dev.deltafuse.bench.workflow.query;

import dev.deltafuse.bench.contracts.CanonicalJson;
import dev.deltafuse.bench.contracts.JsonArr;
import dev.deltafuse.bench.contracts.JsonBool;
import dev.deltafuse.bench.contracts.JsonNull;
import dev.deltafuse.bench.contracts.JsonNum;
import dev.deltafuse.bench.contracts.JsonObj;
import dev.deltafuse.bench.contracts.JsonStr;
import dev.deltafuse.bench.contracts.JsonValue;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import javax.sql.DataSource;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

/**
 * Read-only projection of the workflow state of one document. It never
 * mutates state and never replays topics; the canonical flow query in the
 * document service aggregates it through its projection client. The
 * sequence is the workflow aggregate watermark (route creation and decision
 * events) of that document, zero before any route exists.
 */
@RestController
public final class WorkflowProjectionController {

    private final DataSource dataSource;

    public WorkflowProjectionController(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    @GetMapping(value = "/api/workflows/documents/{documentId}/projection",
                produces = MediaType.APPLICATION_JSON_VALUE)
    public String projection(@PathVariable("documentId") String documentId) {
        String routeId = null;
        String state = null;
        String approverActorId = null;
        long sequence = 0;
        try (Connection connection = dataSource.getConnection()) {
            connection.setReadOnly(true);
            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT route_id, state, approver_actor_id FROM route "
                    + "WHERE document_id = ? ORDER BY created_at DESC, route_id DESC LIMIT 1")) {
                statement.setString(1, documentId);
                try (ResultSet rows = statement.executeQuery()) {
                    if (rows.next()) {
                        routeId = rows.getString(1);
                        state = rows.getString(2);
                        approverActorId = rows.getString(3);
                    }
                }
            }
            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT COALESCE(MAX(domain_sequence), 0) FROM outbox_event "
                    + "WHERE aggregate_type = 'ROUTE' AND payload->>'document_id' = ?")) {
                statement.setString(1, documentId);
                try (ResultSet rows = statement.executeQuery()) {
                    if (rows.next()) {
                        sequence = rows.getLong(1);
                    }
                }
            }
        } catch (SQLException failure) {
            throw new IllegalStateException("workflow projection unavailable", failure);
        }
        List<JsonValue> slots = new ArrayList<>();
        if (routeId != null && "PENDING".equals(state)) {
            slots.add(JsonObj.of(Map.of(
                    "assigned_actor_id", new JsonStr(approverActorId),
                    "role", new JsonStr("approver"))));
        }
        Map<String, JsonValue> members = new LinkedHashMap<>();
        members.put("available", new JsonBool(true));
        members.put("open_slots", new JsonArr(slots));
        members.put("route_id", routeId == null ? JsonNull.INSTANCE : new JsonStr(routeId));
        members.put("sequence", new JsonNum(sequence));
        members.put("state", state == null ? JsonNull.INSTANCE : new JsonStr(state));
        return CanonicalJson.write(JsonObj.of(members));
    }
}
