package com.financial.aeo.orchestrator.web;

import com.financial.aeo.orchestrator.config.AeoProperties;
import jakarta.servlet.http.HttpServletRequest;
import java.net.URI;
import java.util.List;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

/**
 * Transparent REST gateway: every /api/** route that is not owned by the orchestrator
 * (more specific mappings win) is forwarded to the NLP worker, preserving method,
 * query string, body, content type and download headers.
 */
@RestController
public class WorkerProxyController {
    private static final List<String> PASS_HEADERS = List.of(HttpHeaders.CONTENT_TYPE, HttpHeaders.CONTENT_DISPOSITION);
    private final RestClient worker;
    private final String base;

    public WorkerProxyController(RestClient workerClient, AeoProperties props) {
        this.worker = workerClient;
        this.base = props.workerUrl().replaceAll("/+$", "");
    }

    @RequestMapping("/api/**")
    public ResponseEntity<byte[]> proxy(HttpServletRequest request, @RequestBody(required = false) byte[] body) {
        String qs = request.getQueryString();
        URI target = URI.create(base + request.getRequestURI() + (qs == null ? "" : "?" + qs));
        RestClient.RequestBodySpec spec = worker.method(HttpMethod.valueOf(request.getMethod())).uri(target)
                .headers(h -> {
                    if (request.getContentType() != null) {
                        h.set(HttpHeaders.CONTENT_TYPE, request.getContentType());
                    }
                    h.set("X-Forwarded-By", "aeo-orchestrator");
                });
        if (body != null && body.length > 0) {
            spec = spec.body(body);
        }
        return spec.exchange((req, res) -> {
            HttpHeaders out = new HttpHeaders();
            for (String h : PASS_HEADERS) {
                String v = res.getHeaders().getFirst(h);
                if (v != null) {
                    out.set(h, v);
                }
            }
            byte[] bytes = res.getBody().readAllBytes();
            return ResponseEntity.status(res.getStatusCode()).headers(out).body(bytes);
        });
    }
}
