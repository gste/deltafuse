-- One database per service, owned by that service's principal. Ownership
-- grants CREATE on the public schema (PostgreSQL 15+), so each owner runs
-- its own Flyway history. CONNECT is revoked from PUBLIC so a service
-- principal cannot open a session on another service's database; the judge
-- role keeps read-only CONNECT.
CREATE DATABASE j03_document OWNER j03_document_app;
CREATE DATABASE j03_workflow OWNER j03_workflow_app;
CREATE DATABASE j03_audit OWNER j03_audit_app;

REVOKE CONNECT ON DATABASE j03_document, j03_workflow, j03_audit FROM PUBLIC;

GRANT CONNECT ON DATABASE j03_document TO j03_judge_readonly;
GRANT CONNECT ON DATABASE j03_workflow TO j03_judge_readonly;
GRANT CONNECT ON DATABASE j03_audit TO j03_judge_readonly;
