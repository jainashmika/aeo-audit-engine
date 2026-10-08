package com.financial.aeo.orchestrator.config;

import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "aeo")
public record AeoProperties(
        String workerUrl,
        String webhookSecret,
        String demoBaseUrl,
        Scheduler scheduler,
        List<DefaultSchedule> defaultSchedules) {

    public record Scheduler(long tickMs) {}

    public record DefaultSchedule(String institution, String path, String entity, String namespace, int intervalMinutes) {}
}
