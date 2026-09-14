package dev.deltafuse.bench.audit.query;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
@RestController
public final class AuditQueryController {
    private final AuditQueryService service;
    public AuditQueryController(AuditQueryService service){this.service=service;}
    @GetMapping(value="/api/audit/documents/{documentId}",produces=MediaType.APPLICATION_JSON_VALUE)
    public String trail(@PathVariable("documentId")String documentId){return service.trail(documentId);}
}
