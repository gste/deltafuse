package dev.deltafuse.bench.contracts;

/** A contract value that serializes to canonical JSON. */
public interface JsonWritable {
    JsonObj toJson();
}
