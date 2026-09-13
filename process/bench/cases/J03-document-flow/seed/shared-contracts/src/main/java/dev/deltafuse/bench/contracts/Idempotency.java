package dev.deltafuse.bench.contracts;

/**
 * Baseline idempotency contract: a repeated operation key with the same
 * canonical payload returns the prior observable result and adds no effect;
 * the same key with a different canonical payload is
 * {@link ErrorCode#IDEMPOTENCY_CONFLICT}, not an infrastructure retry.
 * Equality is canonical parsed-field equality, never raw member order.
 */
public final class Idempotency {

    private Idempotency() {
    }

    /** True when both payloads are parsed-equal under canonical serialization. */
    public static boolean samePayload(String storedPayloadJson, String incomingPayloadJson) {
        String stored = CanonicalJson.write(CanonicalJson.parse(storedPayloadJson));
        String incoming = CanonicalJson.write(CanonicalJson.parse(incomingPayloadJson));
        return stored.equals(incoming);
    }

    public static void requireSamePayload(String operationId, String storedPayloadJson, String incomingPayloadJson) {
        if (!samePayload(storedPayloadJson, incomingPayloadJson)) {
            throw new ContractViolation(ErrorCode.IDEMPOTENCY_CONFLICT,
                    "operation " + operationId + " replayed with a different payload");
        }
    }
}
