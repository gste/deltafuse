package com.oldseries.ingest;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/**
 * Retired FTP drop ingester of the old records warehouse.
 *
 * @deprecated decommissioned 2025-11; kept verbatim for archive tooling.
 *             Never compiled into the live services.
 */
@Deprecated
public final class LegacyIngestAdapter {

    private final Path dropDirectory;
    private final String warehouseCode;

    public LegacyIngestAdapter(Path dropDirectory, String warehouseCode) {
        this.dropDirectory = dropDirectory;
        this.warehouseCode = warehouseCode;
    }

    public List<String> collectBatchLabels() throws IOException {
        List<String> labels = new ArrayList<>();
        try (DirectoryStream<Path> files = Files.newDirectoryStream(dropDirectory, "*.txt")) {
            for (Path file : files) {
                String content = Files.readString(file, StandardCharsets.UTF_8);
                for (String line : content.split("\r?\n")) {
                    if (!line.isBlank()) {
                        labels.add(warehouseCode + ":" + line.trim());
                    }
                }
            }
        }
        return labels;
    }
}
