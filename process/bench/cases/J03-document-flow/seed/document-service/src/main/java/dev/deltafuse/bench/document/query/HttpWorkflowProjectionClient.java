package dev.deltafuse.bench.document.query;

import dev.deltafuse.bench.contracts.CanonicalJson;
import dev.deltafuse.bench.contracts.JsonValue;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

/**
 * HTTP projection client of the workflow service document projection. A 200
 * response is available; route identity stays null until the route has been
 * created, and the sequence is the workflow aggregate watermark of the
 * document.
 */
public final class HttpWorkflowProjectionClient implements WorkflowProjectionClient {

    private final HttpClient http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(3))
            .build();
    private final String baseUrl;

    public HttpWorkflowProjectionClient(String baseUrl) {
        this.baseUrl = baseUrl.replaceAll("/$", "");
    }

    @Override
    public WorkflowProjection read(String documentId) {
        dev.deltafuse.bench.contracts.JsonObj body =
                fetch(URI.create(baseUrl + "/api/workflows/documents/"
                        + documentId + "/projection")).asObj();
        String routeId = body.getOptionalString("route_id");
        String state = body.getOptionalString("state");
        List<OpenSlot> slots = new ArrayList<>();
        for (JsonValue item : ((dev.deltafuse.bench.contracts.JsonArr)
                body.member("open_slots")).items()) {
            dev.deltafuse.bench.contracts.JsonObj slot =
                    (dev.deltafuse.bench.contracts.JsonObj) item;
            slots.add(new OpenSlot(slot.getString("role"),
                    slot.getString("assigned_actor_id")));
        }
        return new WorkflowProjection(true, routeId, state,
                body.getLong("sequence"), List.copyOf(slots));
    }

    private dev.deltafuse.bench.contracts.JsonObj fetch(URI uri) {
        try {
            HttpResponse<String> response = http.send(
                    HttpRequest.newBuilder(uri).GET()
                            .timeout(Duration.ofSeconds(5)).build(),
                    HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() != 200) {
                throw new IllegalStateException(
                        "workflow projection returned " + response.statusCode());
            }
            return CanonicalJson.parse(response.body()).asObj();
        } catch (InterruptedException failure) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("workflow projection interrupted", failure);
        } catch (java.io.IOException failure) {
            throw new IllegalStateException("workflow projection unreachable", failure);
        }
    }
}
