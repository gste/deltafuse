-- Cluster-wide principals of the baseline seed. Roles are created NOLOGIN:
-- credentials are injected at runtime by the provisioning context (Compose
-- pins its own via environment; tests generate throwaway passwords). No
-- secret value is ever committed.
CREATE ROLE j03_document_app NOLOGIN;
CREATE ROLE j03_workflow_app NOLOGIN;
CREATE ROLE j03_audit_app NOLOGIN;
CREATE ROLE j03_judge_readonly NOLOGIN;
