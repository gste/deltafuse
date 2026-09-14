package dev.deltafuse.bench.document.legacy;

import java.util.List;

/** One nightly import batch of the retired scanner pipeline. */
public record LegacyImportBatch(String batchId, List<LegacyDocumentSummary> documents,
        String operatorName) {

    public LegacyImportBatch {
        documents = List.copyOf(documents);
    }

    public int totalPages() {
        return documents.stream().mapToInt(LegacyDocumentSummary::pageCount).sum();
    }
}
