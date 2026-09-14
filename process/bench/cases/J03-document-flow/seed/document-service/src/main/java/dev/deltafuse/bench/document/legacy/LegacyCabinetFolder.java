package dev.deltafuse.bench.document.legacy;

/** A folder of the physical cabinet tree referenced by the old importer. */
public final class LegacyCabinetFolder {

    private final String code;
    private final String parentCode;
    private int capacityUsed;

    public LegacyCabinetFolder(String code, String parentCode, int capacityUsed) {
        this.code = code;
        this.parentCode = parentCode;
        this.capacityUsed = capacityUsed;
    }

    public String code() {
        return code;
    }

    public String parentCode() {
        return parentCode;
    }

    public boolean hasCapacity() {
        return capacityUsed < 200;
    }

    public void fileOneMore() {
        capacityUsed++;
    }
}
