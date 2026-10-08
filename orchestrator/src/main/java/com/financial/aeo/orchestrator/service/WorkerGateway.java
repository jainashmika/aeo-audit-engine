package com.financial.aeo.orchestrator.service;

import java.util.List;
import java.util.Map;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

/** Typed calls into the Python NLP & vector worker. */
@Service
public class WorkerGateway {
    private static final ParameterizedTypeReference<Map<String, Object>> MAP = new ParameterizedTypeReference<>() {};
    private static final ParameterizedTypeReference<List<Map<String, Object>>> LIST = new ParameterizedTypeReference<>() {};
    private final RestClient worker;

    public WorkerGateway(RestClient workerClient) {
        this.worker = workerClient;
    }

    public Map<String, Object> health() {
        return worker.get().uri("/api/health").retrieve().body(MAP);
    }

    public Map<String, Object> scrape(String institution, String url, String entity, String namespace) {
        Map<String, Object> body = new java.util.HashMap<>();
        body.put("institution", institution);
        body.put("url", url);
        body.put("entity", entity);
        body.put("namespace", namespace);
        return worker.post().uri("/api/scrape").contentType(MediaType.APPLICATION_JSON).body(body).retrieve().body(MAP);
    }

    public Map<String, Object> validate() {
        return worker.post().uri("/api/validation/run").retrieve().body(MAP);
    }

    public Map<String, Object> partition(String institution) {
        return worker.post().uri("/api/institutions/{slug}/partition", institution).retrieve().body(MAP);
    }

    public List<Map<String, Object>> institutions() {
        return worker.get().uri("/api/institutions").retrieve().body(LIST);
    }

    public List<Map<String, Object>> entities(String slug) {
        return worker.get().uri("/api/institutions/{slug}/entities", slug).retrieve().body(LIST);
    }
}
