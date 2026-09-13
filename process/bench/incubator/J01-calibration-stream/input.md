# User request: retroactive calibration of industrial telemetry

The system currently stores every raw sensor measurement with identity
calibration. Add versioned calibration profiles without replacing Kafka with a
direct service call.

## Required behavior

1. A profile has `profile_id`, `sensor_id`, `effective_from`, `scale`, and
   `offset`. For a measurement captured at `t`, use the profile for the same
   sensor with the greatest `effective_from <= t`. If none exists, retain the
   identity calibration.
2. Calculate `calibrated_value = raw_value * scale + offset` using decimal
   arithmetic and round only the final value to three places with `HALF_UP`.
3. Repeating a `measurement_id` MUST have no additional database or event
   effect.
4. Profiles may arrive after measurements. A new profile MUST recalculate the
   affected stored interval until the next profile for that sensor.
5. Emit one `MeasurementCorrected` event only when a stored value changes.
   Repeating a profile event MUST emit no duplicate corrections.
6. Profile persistence, recalculation, and correction-outbox creation MUST be
   atomic. Publishing may be retried, but the observable effect is idempotent.
7. Sensors are independent. Invalid events go to the existing dead-letter
   topic without partially changing calibration state.
8. Preserve the HTTP ingestion contract and identity behavior for sensors
   without a profile.

Do not introduce Redis, external HTTP calls, wall-clock decisions, or a shared
database transaction between services.
