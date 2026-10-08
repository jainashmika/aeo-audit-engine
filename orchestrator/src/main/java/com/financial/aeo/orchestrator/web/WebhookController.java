package com.financial.aeo.orchestrator.web;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.financial.aeo.orchestrator.service.JobService;
import com.financial.aeo.orchestrator.service.WebhookService;
import com.financial.aeo.orchestrator.service.WorkerGateway;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Banking portals call this when a product page, rate card or filing changes.
 * Body: {"institution":"meridian","url":"...","entity":"meridian-nifty-dividend-etf","namespace":"Retail"}
 * The re-scrape updates the temporal graph, which supersedes the prior ground truth.
 */
@RestController
@RequestMapping("/api/webhooks")
public class WebhookController {
    private final WebhookService webhooks;
    private final JobService jobs;
    private final WorkerGateway worker;
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;

    public WebhookController(WebhookService webhooks, JobService jobs, WorkerGateway worker, JdbcTemplate jdbc,
                             ObjectMapper mapper) {
        this.webhooks = webhooks;
        this.jobs = jobs;
        this.worker = worker;
        this.jdbc = jdbc;
        this.mapper = mapper;
    }

    @PostMapping("/portal-update")
    public ResponseEntity<Map<String, Object>> portalUpdate(@RequestBody byte[] body,
                                                            @RequestHeader(value = "X-AEO-Signature", required = false) String sig)
            throws IOException {
        boolean ok = webhooks.verify(body, sig);
        JsonNode json = mapper.readTree(body);
        jdbc.update("INSERT INTO webhook_events(source, signature_ok, body) VALUES (?, ?, ?::jsonb)",
                json.path("institution").asText("unknown"), ok, mapper.writeValueAsString(json));
        if (!ok) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("error", "invalid signature"));
        }
        String inst = json.path("institution").asText();
        String url = json.path("url").asText();
        if (inst.isBlank() || url.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "institution and url are required"));
        }
        String entity = json.hasNonNull("entity") ? json.get("entity").asText() : null;
        String ns = json.hasNonNull("namespace") ? json.get("namespace").asText() : null;
        Map<String, Object> req = new HashMap<>();
        req.put("institution", inst);
        req.put("url", url);
        req.put("trigger", "webhook");
        UUID job = jobs.submit("webhook_scrape", req, () -> {
            Map<String, Object> scrape = worker.scrape(inst, url, entity, ns);
            worker.partition(inst);
            return scrape;
        });
        return ResponseEntity.accepted().body(Map.of("job", job));
    }
}
