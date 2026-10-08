package com.financial.aeo.orchestrator.web;

import com.financial.aeo.orchestrator.service.JobService;
import com.financial.aeo.orchestrator.service.ScheduleService;
import com.financial.aeo.orchestrator.service.WorkerGateway;
import java.util.List;
import java.util.Map;
import org.springframework.graphql.data.method.annotation.Argument;
import org.springframework.graphql.data.method.annotation.MutationMapping;
import org.springframework.graphql.data.method.annotation.QueryMapping;
import org.springframework.stereotype.Controller;

@Controller
public class AuditGraphQlController {
    private final WorkerGateway worker;
    private final JobService jobs;
    private final ScheduleService schedules;

    public AuditGraphQlController(WorkerGateway worker, JobService jobs, ScheduleService schedules) {
        this.worker = worker;
        this.jobs = jobs;
        this.schedules = schedules;
    }

    @QueryMapping
    public List<Map<String, Object>> institutions() {
        return worker.institutions();
    }

    @QueryMapping
    public List<Map<String, Object>> entities(@Argument String institution) {
        return worker.entities(institution);
    }

    @QueryMapping
    public List<Map<String, Object>> jobs(@Argument Integer limit) {
        return jobs.recent(limit == null ? 20 : Math.min(limit, 200));
    }

    @QueryMapping
    public List<Map<String, Object>> schedules() {
        return schedules.list();
    }

    @MutationMapping
    public String runValidation() {
        return jobs.submit("validation", Map.of("trigger", "graphql"), worker::validate).toString();
    }

    @MutationMapping
    public String scheduleScrape(@Argument String institution, @Argument String url, @Argument String entity,
                                 @Argument String namespace, @Argument Integer intervalMinutes) {
        return schedules.create(institution, url, entity, namespace, intervalMinutes == null ? 60 : intervalMinutes)
                .toString();
    }
}
