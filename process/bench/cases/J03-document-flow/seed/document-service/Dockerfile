FROM eclipse-temurin@sha256:66bb900643426ad01996d25bada7d56751913f9cec3b827fcb715d2ec9a0fbfc
WORKDIR /app
COPY document-service/target/classes/ classes/
COPY document-service/target/dependency/ lib/
USER 10001:10001
ENTRYPOINT ["java","-cp","/app/classes:/app/lib/*","dev.deltafuse.bench.document.DocumentServiceApplication"]
