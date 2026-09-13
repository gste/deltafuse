# J01 calibration stream seed

Incubator seed for a Java system benchmark. It stays outside
`process/bench/cases` until the scorer can execute Java/system cases.

The working baseline has two Spring Boot services:

- `telemetry-gateway` accepts raw measurements over HTTP and publishes Kafka;
- `calibration-service` consumes them and stores identity-calibrated values in
  PostgreSQL.

The target Change in `input.md` adds versioned calibration profiles,
retroactive corrections, and exactly-once effects under duplicate delivery.
The future judge owns generated event streams and the black-box oracle.

```text
mvn -B test
docker compose up --build
```

The Maven build is independent of Docker. The Compose stack currently defines
Kafka and PostgreSQL; service images and the hidden judge are promotion work.
