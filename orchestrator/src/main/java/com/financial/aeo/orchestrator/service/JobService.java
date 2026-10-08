package com.financial.aeo.orchestrator.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Supplier;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/** Durable bookkeeping for every orchestrated unit of work (scrapes, webhooks, QA runs). */
@Service
public class JobService {
    private static final Logger log = LoggerFactory.getLogger(JobService.class);
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;
    private final ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();

    public JobService(JdbcTemplate jdbc, ObjectMapper mapper) {
        this.jdbc = jdbc;
        this.mapper = mapper;
    }

    public UUID submit(String kind, Map<String, Object> request, Supplier<Object> work) {
        UUID id = UUID.randomUUID();
        jdbc.update("INSERT INTO orchestration_jobs(id, kind, status, request) VALUES (?, ?, 'running', ?::jsonb)",
                id, kind, json(request));
        executor.submit(() -> {
            try {
                Object result = work.get();
                finish(id, "succeeded", result);
            } catch (Exception e) {
                log.warn("job {} ({}) failed: {}", id, kind, e.getMessage());
                finish(id, "failed", Map.of("error", String.valueOf(e.getMessage())));
            }
        });
        return id;
    }

    private void finish(UUID id, String status, Object result) {
        jdbc.update("UPDATE orchestration_jobs SET status = ?, result = ?::jsonb, finished_at = now() WHERE id = ?",
                status, json(result), id);
    }

    public List<Map<String, Object>> recent(int limit) {
        return jdbc.queryForList("""
                SELECT id::text AS id, kind, status, request::text AS request, created_at::text AS created_at,
                       finished_at::text AS finished_at
                FROM orchestration_jobs ORDER BY created_at DESC LIMIT ?""", limit);
    }

    public Map<String, Object> counts() {
        return jdbc.queryForMap("""
                SELECT count(*) FILTER (WHERE status = 'running')   AS running,
                       count(*) FILTER (WHERE status = 'succeeded') AS succeeded,
                       count(*) FILTER (WHERE status = 'failed')    AS failed
                FROM orchestration_jobs""");
    }

    private String json(Object o) {
        try {
            return mapper.writeValueAsString(o);
        } catch (JsonProcessingException e) {
            return "{}";
        }
    }
}
