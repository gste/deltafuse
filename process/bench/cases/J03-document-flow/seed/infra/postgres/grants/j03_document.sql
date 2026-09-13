-- Read-only judge access inside j03_document. Run as the database owner
-- after migrations so every existing table is covered and future tables
-- inherit the grant. No INSERT/UPDATE/DELETE/DDL privilege is granted.
GRANT USAGE ON SCHEMA public TO j03_judge_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO j03_judge_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO j03_judge_readonly;
