# monitoring.usage_stats

## REQ-US-01 Record

UsageRecorder MUST accept record(event) calls for non-empty string event names and count each occurrence per event name.

## REQ-US-02 Unknown state

A new UsageRecorder MUST start with no recorded events; counts() MUST return an empty mapping.

## REQ-US-03 counts

counts() MUST return a mapping of event name to its recorded call count.
