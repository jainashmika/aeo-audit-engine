package com.financial.aeo.orchestrator.service;

import com.financial.aeo.orchestrator.config.AeoProperties;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/** Automated scraping: due schedules are turned into scrape jobs on every tick. */
@Service
public class ScheduleService {
    private static final Logger log = LoggerFactory.getLogger(ScheduleService.class);
    private final JdbcTemplate jdbc;
    private final JobService jobs;
    private final WorkerGateway worker;
    private final AeoProperties props;

    public ScheduleService(JdbcTemplate jdbc, JobService jobs, WorkerGateway worker, AeoProperties props) {
        this.jdbc = jdbc;
        this.jobs = jobs;
        this.worker = worker;
        this.props = props;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void bootstrapDefaults() {
        Integer n = jdbc.queryForObject("SELECT count(*) FROM scrape_schedules", Integer.class);
        if (n != null && n > 0 || props.defaultSchedules() == null) {
            return;
        }
        String base = props.demoBaseUrl().replaceAll("/+$", "");
        for (AeoProperties.DefaultSchedule s : props.defaultSchedules()) {
            create(s.institution(), base + "/" + s.path(), s.entity(), s.namespace(), s.intervalMinutes());
        }
        log.info("registered {} default scrape schedules", props.defaultSchedules().size());
    }

    public UUID create(String institution, String url, String entity, String namespace, int intervalMinutes) {
        UUID id = UUID.randomUUID();
        jdbc.update("""
                INSERT INTO scrape_schedules(id, institution_slug, url, entity_slug, namespace_type, interval_minutes, last_run_at)
                VALUES (?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (institution_slug, url) DO UPDATE SET interval_minutes = EXCLUDED.interval_minutes,
                    entity_slug = EXCLUDED.entity_slug, namespace_type = EXCLUDED.namespace_type, enabled = true""",
                id, institution, url, entity, namespace, intervalMinutes);
        return id;
    }

    public List<Map<String, Object>> list() {
        return jdbc.queryForList("""
                SELECT id::text AS id, institution_slug, url, entity_slug, namespace_type, interval_minutes, enabled,
                       last_run_at::text AS last_run_at,
                       (last_run_at + make_interval(mins => interval_minutes))::text AS next_run_at
                FROM scrape_schedules ORDER BY institution_slug, url""");
    }

    public void setEnabled(UUID id, boolean enabled) {
        jdbc.update("UPDATE scrape_schedules SET enabled = ? WHERE id = ?", enabled, id);
    }

    public UUID runNow(UUID id) {
        Map<String, Object> s = jdbc.queryForMap("SELECT * FROM scrape_schedules WHERE id = ?", id);
        return dispatch(s);
    }

    @Scheduled(fixedDelayString = "${aeo.scheduler.tick-ms:60000}", initialDelay = 30_000)
    public void tick() {
        List<Map<String, Object>> due = jdbc.queryForList("""
                SELECT * FROM scrape_schedules
                WHERE enabled AND (last_run_at IS NULL OR last_run_at + make_interval(mins => interval_minutes) <= now())""");
        due.forEach(this::dispatch);
    }

    private UUID dispatch(Map<String, Object> s) {
        jdbc.update("UPDATE scrape_schedules SET last_run_at = now() WHERE id = ?", s.get("id"));
        String inst = (String) s.get("institution_slug");
        String url = (String) s.get("url");
        Map<String, Object> req = new java.util.HashMap<>();
        req.put("institution", inst);
        req.put("url", url);
        req.put("trigger", "schedule");
        return jobs.submit("scheduled_scrape", req,
                () -> worker.scrape(inst, url, (String) s.get("entity_slug"), (String) s.get("namespace_type")));
    }
}
