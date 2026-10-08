# Risk Validation Report

_AEO Audit Engine, generated 2026-10-08T18:11:50Z. NLP backend: feature-hashing-768 (lite) / finance-lexicon (lite)._

**8 of 8 edge cases pass.**

This report demonstrates that deterministic text transformations (temporal re-weighting, namespace partitioning, Machine Hub payloads) constrain the specific failure each case describes. Every figure below is computed live from the temporal knowledge graph.

## PASS: handles factual staleness vs mass-market data

- [x] ground truth is 5%
- [x] naive LLM prior answers 2%
- [x] GraphRAG answers 5%
- [x] corroboration deficit > 0.9
- [x] replaces payload asserts 5% over 2%

```json
{
  "claims": 10044,
  "stale_claims": 10031,
  "naive_gt_share": 0.00132,
  "temporal_gt_share": 0.648203,
  "corroboration_deficit": 0.99868
}
```

## PASS: bypasses vector sparsity in gated calculators

- [x] plain-text crawler sees zero rates
- [x] headless execution recovers 8.65%
- [x] extraction loss reported as 100%
- [x] Machine Hub has flat Markdown with rate

```json
{
  "render_mode": "xhr-interceptor",
  "extraction_loss": 1.0,
  "static_tokens": 26,
  "rendered_tokens": 68
}
```

## PASS: quantifies context severance on AI referral

- [x] landing = generic homepage
- [x] CSS > 0.75
- [x] best match is the ESG fund page
- [x] hydration script carries 0.42%

```json
{
  "context_severance_score": 0.9605,
  "best_match_distance": 0.6532,
  "intent_gap": 0.3073,
  "backend": "feature-hashing-768 (lite)"
}
```

## PASS: prevents semantic dilution across brands

- [x] brand-level retrieval hallucinates 1.25%
- [x] partitioned retrieval answers 0.45%
- [x] attribute bleed detected
- [x] matrix contrasts 1.25% vs 0.45%

```json
{
  "semantic_dilution_index": 0.5067,
  "attribute_bleed": 0.9722,
  "brand_votes": {
    "0.45": 62.18,
    "1.25": 242.87
  }
}
```

## PASS: handles dynamic payload obfuscation

- [x] static DOM exposes no APR
- [x] XHR JSON intercepted
- [x] latent APR 13.49% extracted
- [x] base64 PDF blob discarded

```json
{
  "render_mode": "xhr-interceptor",
  "intercepted_responses": 1
}
```

## PASS: mitigates zero-vector extraction

- [x] sparse page triggers fallback
- [x] linked SEBI filing crawled
- [x] financial-facts.json populated (TER 0.38%)

```json
{
  "static_tokens": 17,
  "filings": [
    {
      "url": "http://localhost:8000/demo-sites/kaveri/filings/sid-kaveri-arbitrage.html",
      "chars": 438
    }
  ]
}
```

## PASS: resolves simultaneous contradictory ground truths

- [x] two official values, same timestamp
- [x] legal disclaimer (0.35%) wins
- [x] marketing tagline (0.20%) demoted

```json
{
  "candidates": [
    {
      "value": 0.35,
      "confidence": 0.8822,
      "status": "active"
    },
    {
      "value": 0.2,
      "confidence": 0.4486,
      "status": "superseded"
    }
  ]
}
```

## PASS: serves payloads deterministically

- [x] Markdown/JSON-LD byte-identical across runs
- [x] ZIP byte-identical across runs

```json
{
  "files": 16,
  "zip_sha256": "18e6ca2e451d7a96"
}
```

## Method notes

- **Corroboration Deficit** = 1 minus the ground truth's share of naive mass, where naive mass per claim is 1 + ln(1 + inbound links) with no time awareness (a proxy for an LLM's statistical prior).
- **Temporal weighting** multiplies each claim by source authority, exponential decay (forum half-life 90 days) and a supersession penalty of 0.9 for values contradicting a newer ground truth.
- **Context Severance Score** is the cosine distance between query and landing-page embeddings; hydration triggers above 0.75.
- **Semantic Dilution Index** = sim(brand, retail centroid) / (sim(brand, retail) + sim(brand, institutional)); **attribute bleed** is the share of third-party claims about institutional products carrying a retail value.
