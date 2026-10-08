package com.financial.aeo.orchestrator;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.financial.aeo.orchestrator.config.AeoProperties;
import com.financial.aeo.orchestrator.service.WebhookService;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;

class WebhookServiceTest {
    private final WebhookService svc = new WebhookService(
            new AeoProperties("http://w", "s3cret", "http://w/demo-sites", new AeoProperties.Scheduler(60000), null));

    @Test
    void acceptsValidSignatureAndRejectsTampering() {
        byte[] body = "{\"institution\":\"meridian\"}".getBytes(StandardCharsets.UTF_8);
        String sig = svc.sign(body);
        assertTrue(svc.verify(body, sig));
        assertFalse(svc.verify("{\"institution\":\"evil\"}".getBytes(StandardCharsets.UTF_8), sig));
        assertFalse(svc.verify(body, null));
    }
}
