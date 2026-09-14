package dev.deltafuse.bench.document;

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

class DocumentControllerTest {
    private DocumentCommandService commands;
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        commands = org.mockito.Mockito.mock(DocumentCommandService.class);
        mvc = MockMvcBuilders.standaloneSetup(new DocumentController(commands)).build();
    }

    @Test
    void create_endpoint_uses_public_snake_case_and_returns_stable_result() throws Exception {
        when(commands.createDocument("op-api-1", "evt-api-1", "doc-api-1", "Policy"))
                .thenReturn(new CommandResult("op-api-1", "doc-api-1", null, "DRAFT", "evt-api-1", 1));

        mvc.perform(post("/api/documents")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"operation_id":"op-api-1","event_id":"evt-api-1",\
                                "document_id":"doc-api-1","title":"Policy"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.operation_id").value("op-api-1"))
                .andExpect(jsonPath("$.document_id").value("doc-api-1"))
                .andExpect(jsonPath("$.version_id").doesNotExist())
                .andExpect(jsonPath("$.domain_sequence").value(1));
        verify(commands).createDocument("op-api-1", "evt-api-1", "doc-api-1", "Policy");
    }

    @Test
    void submit_identity_mismatch_returns_public_error_without_calling_service() throws Exception {
        mvc.perform(post("/api/documents/doc-path/versions/ver-path/submit")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"operation_id":"op-api-2","event_id":"evt-api-2",\
                                "document_id":"doc-other","version_id":"ver-path"}
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("IDENTITY_MISMATCH"))
                .andExpect(jsonPath("$.operation_id").value("op-api-2"))
                .andExpect(jsonPath("$.details").isEmpty());
        verifyNoInteractions(commands);
    }

    @Test
    void unknown_request_member_is_invalid_schema_and_never_reaches_service() throws Exception {
        mvc.perform(post("/api/documents")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"operation_id":"op-api-3","event_id":"evt-api-3",\
                                "document_id":"doc-api-3","title":"Policy","target_role":"registrar"}
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_SCHEMA"))
                .andExpect(jsonPath("$.operation_id").value("op-api-3"));
        verifyNoInteractions(commands);
    }
}
