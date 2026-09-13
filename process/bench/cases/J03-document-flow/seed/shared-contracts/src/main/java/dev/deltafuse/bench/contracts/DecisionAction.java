package dev.deltafuse.bench.contracts;

import java.util.Set;

/**
 * Decision actions carried by a baseline decision. Any other action string is
 * {@code UNSUPPORTED_ACTION}: retained as invalid evidence, never a state
 * transition.
 */
public enum DecisionAction {
    APPROVE,
    REJECT;

    public static Set<String> vocabulary() {
        return Set.of(APPROVE.name(), REJECT.name());
    }

    public static DecisionAction parse(String value) {
        for (DecisionAction action : values()) {
            if (action.name().equals(value)) {
                return action;
            }
        }
        throw new ContractViolation(ErrorCode.UNSUPPORTED_ACTION, "unsupported decision action: " + value);
    }
}
