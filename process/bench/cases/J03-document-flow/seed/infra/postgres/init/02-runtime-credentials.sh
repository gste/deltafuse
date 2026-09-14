#!/usr/bin/env bash
set -euo pipefail
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -v ON_ERROR_STOP=1 \
  --set=document_password="$J03_DOCUMENT_DB_PASSWORD" \
  --set=workflow_password="$J03_WORKFLOW_DB_PASSWORD" \
  --set=audit_password="$J03_AUDIT_DB_PASSWORD" \
  --set=judge_password="$J03_JUDGE_DB_PASSWORD" <<'SQL'
ALTER ROLE j03_document_app LOGIN PASSWORD :'document_password';
ALTER ROLE j03_workflow_app LOGIN PASSWORD :'workflow_password';
ALTER ROLE j03_audit_app LOGIN PASSWORD :'audit_password';
ALTER ROLE j03_judge_readonly LOGIN PASSWORD :'judge_password';
SQL
for database in j03_document j03_workflow j03_audit; do
  owner="${database}_app"
  psql --username "$POSTGRES_USER" --dbname "$database" -v ON_ERROR_STOP=1 <<SQL
SET ROLE ${owner};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO j03_judge_readonly;
RESET ROLE;
SQL
done
