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
 * HTTP projection client of the audit service trail endpoint. A 200
 * response is available and carries the per-document audit watermark (the
 * highest audited sequence) plus the canonical audit entries.
 */
public final class HttpAuditProjectionClient implements AuditProjectionClient {

    private final HttpClient http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(3))
            .build();
    private final String baseUrl;

    public HttpAuditProjectionClient(String baseUrl) {
        this.baseUrl = baseUrl.replaceAll("/$", "");
    }

    @Override
    public AuditProjection read(String documentId) {
        JsonValue body = fetch(URI.create(baseUrl + "/api/audit/documents/"
                + documentId));
        List<AuditEntry> entries = new ArrayList<>();
        long highest = 0;
        for (JsonValue item : ((dev.deltafuse.bench.contracts.JsonArr) body).items()) {
            dev.deltafuse.bench.contracts.JsonObj entry = (dev.deltafuse.bench.contracts.JsonObj) item;
            long sequence = entry.getLong("sequence");
            highest = Math.max(highest, sequence);
            entries.add(new AuditEntry(sequence, entry.getString("event_id"),
                    entry.getString("kind")));
        }
        return new AuditProjection(true, highest, List.copyOf(entries));
    }

    private JsonValue fetch(URI uri) {
        try {
            HttpResponse<String> response = http.send(
                    HttpRequest.newBuilder(uri).GET()
                            .timeout(Duration.ofSeconds(5)).build(),
                    HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() != 200) {
                throw new IllegalStateException(
                        "audit projection returned " + response.statusCode());
            }
            return CanonicalJson.parse(response.body());
        } catch (InterruptedException failure) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("audit projection interrupted", failure);
        } catch (java.io.IOException failure) {
            throw new IllegalStateException("audit projection unreachable", failure);
        }
    }
}
