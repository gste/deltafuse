package dev.deltafuse.bench.workflow;

import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

class WorkflowControllerTest {
    private WorkflowCommandService commands;
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        commands = org.mockito.Mockito.mock(WorkflowCommandService.class);
        mvc = MockMvcBuilders.standaloneSetup(new WorkflowController(commands)).build();
    }

    @Test
    void decision_endpoint_binds_every_public_identity() throws Exception {
        when(commands.decide("op-api-1", "evt-api-1", "route-api-1", "doc-api-1", "ver-api-1",
                "dec-api-1", "actor-api-1", "approver", "APPROVE"))
                .thenReturn(new DecisionResult("op-api-1", "route-api-1", "dec-api-1",
                        "APPROVED", "evt-api-1", 2));
        mvc.perform(post("/api/workflows/route-api-1/decisions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request("route-api-1", "approver", "APPROVE", "")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.route_id").value("route-api-1"))
                .andExpect(jsonPath("$.state").value("APPROVED"))
                .andExpect(jsonPath("$.domain_sequence").value(2));
        verify(commands).decide("op-api-1", "evt-api-1", "route-api-1", "doc-api-1", "ver-api-1",
                "dec-api-1", "actor-api-1", "approver", "APPROVE");
    }

    @Test
    void path_identity_mismatch_is_public_error_without_transition() throws Exception {
        mvc.perform(post("/api/workflows/route-path/decisions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request("route-other", "approver", "APPROVE", "")))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("IDENTITY_MISMATCH"))
                .andExpect(jsonPath("$.operation_id").value("op-api-1"));
        verifyNoInteractions(commands);
    }

    @Test
    void target_only_member_is_invalid_schema_without_transition() throws Exception {
        mvc.perform(post("/api/workflows/route-api-1/decisions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request("route-api-1", "registrar", "APPROVE", ",\"expert_slot\":\"legal\"")))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_SCHEMA"))
                .andExpect(jsonPath("$.operation_id").value("op-api-1"));
        verifyNoInteractions(commands);
    }

    private static String request(String routeId, String role, String action, String extra) {
        return "{\"operation_id\":\"op-api-1\",\"event_id\":\"evt-api-1\","
                + "\"route_id\":\"" + routeId + "\",\"document_id\":\"doc-api-1\","
                + "\"version_id\":\"ver-api-1\",\"decision_id\":\"dec-api-1\","
                + "\"actor_id\":\"actor-api-1\",\"role\":\"" + role + "\","
                + "\"action\":\"" + action + "\"" + extra + "}";
    }
}
