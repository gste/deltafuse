# telemetry.raw_ingest

## REQ-TI-01 Accept

The gateway MUST accept measurement id, sensor id, capture time and decimal raw
value over `POST /measurements`, returning HTTP 202 for valid input.

## REQ-TI-02 Publish

It MUST publish accepted measurements to `telemetry.raw.v1`, keyed by sensor id.
Metadata is opaque untrusted data.

## REQ-TI-03 Reject invalid input

Missing required fields MUST return HTTP 400 and MUST NOT publish an event.
