package dev.deltafuse.bench.document.query;
import java.util.List;
import javax.sql.DataSource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.context.annotation.*;

@Configuration
public class FlowQueryConfiguration {
    @Bean @ConditionalOnMissingBean WorkflowProjectionClient workflowProjectionClient(
            @Value("${j03.query.workflow-base-url:}") String workflowBaseUrl) {
        if (workflowBaseUrl == null || workflowBaseUrl.isBlank()) {
            return id -> new WorkflowProjectionClient.WorkflowProjection(false, null, null, 0, List.of());
        }
        return new HttpWorkflowProjectionClient(workflowBaseUrl);
    }

    @Bean @ConditionalOnMissingBean AuditProjectionClient auditProjectionClient(
            @Value("${j03.query.audit-base-url:}") String auditBaseUrl) {
        if (auditBaseUrl == null || auditBaseUrl.isBlank()) {
            return id -> new AuditProjectionClient.AuditProjection(false, 0, List.of());
        }
        return new HttpAuditProjectionClient(auditBaseUrl);
    }

    @Bean FlowQueryService flowQueryService(DataSource data, WorkflowProjectionClient workflow, AuditProjectionClient audit) {
        return new FlowQueryService(data, workflow, audit);
    }
}
