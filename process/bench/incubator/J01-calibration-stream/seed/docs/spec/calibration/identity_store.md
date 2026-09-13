# calibration.identity_store

## REQ-CI-01 Consume

The calibration service MUST consume `telemetry.raw.v1` measurements.

## REQ-CI-02 Identity calibration

Until a profile exists, calibrated value MUST equal raw value.

## REQ-CI-03 Duplicate measurement

Repeated delivery of a measurement id MUST NOT create another stored row.
