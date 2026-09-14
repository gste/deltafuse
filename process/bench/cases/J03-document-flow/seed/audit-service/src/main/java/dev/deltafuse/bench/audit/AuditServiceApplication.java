package dev.deltafuse.bench.audit;
import dev.deltafuse.bench.audit.messaging.AuditProjectionService;
import dev.deltafuse.bench.audit.query.AuditQueryService;
import javax.sql.DataSource;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
@SpringBootApplication
public class AuditServiceApplication {
    public static void main(String[]args){SpringApplication.run(AuditServiceApplication.class,args);}
    @Bean AuditProjectionService auditProjectionService(DataSource data){return new AuditProjectionService(data);}
    @Bean AuditQueryService auditQueryService(DataSource data){return new AuditQueryService(data);}
}
