package dev.deltafuse.bench.workflow.legacy;

import java.time.LocalDate;

/** Business-day arithmetic of the retired escalation timer. */
public final class LegacyEscalationTimer {

    private LegacyEscalationTimer() {
    }

    public static LocalDate dueDate(LocalDate filed, int slaDays) {
        LocalDate due = filed;
        int remaining = slaDays;
        while (remaining > 0) {
            due = due.plusDays(1);
            if (due.getDayOfWeek().getValue() < 6) {
                remaining--;
            }
        }
        return due;
    }

    public static boolean overdue(LocalDate today, LocalDate due) {
        return today.isAfter(due);
    }
}
