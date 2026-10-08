package com.financial.aeo.orchestrator.web;

import com.financial.aeo.orchestrator.service.JobService;
import com.financial.aeo.orchestrator.service.ScheduleService;
import com.financial.aeo.orchestrator.service.WorkerGateway;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/orchestrator")
public class OrchestratorController {
    private final JobService jobs;
    private final ScheduleService schedules;
    private final WorkerGateway worker;

    public OrchestratorController(JobService jobs, ScheduleService schedules, WorkerGateway worker) {
        this.jobs = jobs;
        this.schedules = schedules;
        this.worker = worker;
    }

    @GetMapping("/status")
    public Map<String, Object> status() {
        Map<String, Object> out = new HashMap<>();
        out.put("orchestrator", "up");
        out.put("jobs", jobs.counts());
        try {
            out.put("worker", worker.health());
        } catch (Exception e) {
            out.put("worker", Map.of("status", "unreachable", "error", String.valueOf(e.getMessage())));
        }
        return out;
    }

    @GetMapping("/jobs")
    public List<Map<String, Object>> jobs(@RequestParam(defaultValue = "30") int limit) {
        return jobs.recent(Math.min(limit, 200));
    }

    @GetMapping("/schedules")
    public List<Map<String, Object>> schedules() {
        return schedules.list();
    }

    public record ScheduleRequest(@NotBlank String institution, @NotBlank String url, String entity, String namespace,
                                  @Min(5) int intervalMinutes) {}

    @PostMapping("/schedules")
    public Map<String, Object> create(@Valid @RequestBody ScheduleRequest r) {
        UUID id = schedules.create(r.institution(), r.url(), r.entity(), r.namespace(), r.intervalMinutes());
        return Map.of("id", id);
    }

    @PatchMapping("/schedules/{id}")
    public Map<String, Object> toggle(@PathVariable UUID id, @RequestParam boolean enabled) {
        schedules.setEnabled(id, enabled);
        return Map.of("id", id, "enabled", enabled);
    }

    @PostMapping("/schedules/{id}/run")
    public Map<String, Object> runNow(@PathVariable UUID id) {
        return Map.of("job", schedules.runNow(id));
    }

    @PostMapping("/validation")
    public Map<String, Object> validation() {
        return Map.of("job", jobs.submit("validation", Map.of("trigger", "manual"), worker::validate));
    }
}
