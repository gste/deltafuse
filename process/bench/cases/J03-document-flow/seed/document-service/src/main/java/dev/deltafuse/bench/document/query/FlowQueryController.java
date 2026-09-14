package dev.deltafuse.bench.document.query;
import org.springframework.http.MediaType;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.web.bind.annotation.*;
@RestController
@ConditionalOnBean(FlowQueryService.class)
public final class FlowQueryController {
    private final FlowQueryService service;
    public FlowQueryController(FlowQueryService service){this.service=service;}
    @GetMapping(value="/api/documents/{documentId}/flow",produces=MediaType.APPLICATION_JSON_VALUE)
    public String flow(@PathVariable("documentId")String documentId){return service.flow(documentId);}
}
