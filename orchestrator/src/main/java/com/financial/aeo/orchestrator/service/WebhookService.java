package com.financial.aeo.orchestrator.service;

import com.financial.aeo.orchestrator.config.AeoProperties;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.stereotype.Service;

/** HMAC-SHA256 verification for banking-portal webhooks (header: X-AEO-Signature: sha256=<hex>). */
@Service
public class WebhookService {
    private final byte[] secret;

    public WebhookService(AeoProperties props) {
        this.secret = props.webhookSecret().getBytes(StandardCharsets.UTF_8);
    }

    public String sign(byte[] body) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret, "HmacSHA256"));
            return "sha256=" + HexFormat.of().formatHex(mac.doFinal(body));
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    public boolean verify(byte[] body, String header) {
        if (header == null) {
            return false;
        }
        return MessageDigest.isEqual(sign(body).getBytes(StandardCharsets.UTF_8), header.trim().getBytes(StandardCharsets.UTF_8));
    }
}
