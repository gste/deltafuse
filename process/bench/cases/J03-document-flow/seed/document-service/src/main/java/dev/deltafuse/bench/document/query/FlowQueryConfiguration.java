package dev.deltafuse.bench.document.query;
import java.util.List;
import javax.sql.DataSource;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.context.annotation.*;

@Configuration
public class FlowQueryConfiguration {
    @Bean @ConditionalOnMissingBean WorkflowProjectionClient workflowProjectionClient(){return id->new WorkflowProjectionClient.WorkflowProjection(false,null,null,0,List.of());}
    @Bean @ConditionalOnMissingBean AuditProjectionClient auditProjectionClient(){return id->new AuditProjectionClient.AuditProjection(false,0,List.of());}
    @Bean FlowQueryService flowQueryService(DataSource data,WorkflowProjectionClient workflow,AuditProjectionClient audit){return new FlowQueryService(data,workflow,audit);}
}
