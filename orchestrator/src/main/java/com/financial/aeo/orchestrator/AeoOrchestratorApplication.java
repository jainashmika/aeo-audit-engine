package com.financial.aeo.orchestrator;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * Enterprise orchestration layer: webhook ingestion from banking portals, scheduled
 * scraping, job bookkeeping, and the GraphQL/REST surface consumed by the dashboard.
 * Computationally heavy NLP is delegated to the Python worker.
 */
@SpringBootApplication
@EnableScheduling
@ConfigurationPropertiesScan
public class AeoOrchestratorApplication {
    public static void main(String[] args) {
        SpringApplication.run(AeoOrchestratorApplication.class, args);
    }
}
