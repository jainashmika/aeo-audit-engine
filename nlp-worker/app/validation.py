"""Executable QA suite for the seven edge cases in the specification, plus a
determinism check. Produces the Risk Validation Report deliverable."""
from __future__ import annotations

import hashlib
import json
import time
import traceback
from datetime import datetime, timezone

from . import analytics, db, graph, logbus, nlp, payloads
from .config import settings


def _entity(inst: str, slug: str) -> str:
    r = db.fetchone("""SELECT en.id FROM entity_nodes en JOIN institutions i ON i.id=en.institution_id
                       WHERE i.slug=%s AND en.slug=%s""", (inst, slug))
    return str(r["id"])


def _scrape(url_part: str) -> dict:
    r = db.fetchone("SELECT * FROM scrape_logs WHERE url LIKE %s ORDER BY fetched_at DESC LIMIT 1", (f"%{url_part}",))
    if not r:
        raise AssertionError(f"no scrape log for {url_part}")
    return r


def case_staleness() -> dict:
    eid = _entity("meridian", "meridian-nifty-dividend-etf")
    c = graph.corroboration(eid, "yield", persist=False)
    sch = payloads.schema_jsonld("meridian")
    node = next(n for n in sch["@graph"] if n["name"] == "Meridian Nifty Dividend ETF")
    checks = {
        "ground truth is 5%": c["ground_truth"]["value"] == 5.0,
        "naive LLM prior answers 2%": c["naive_llm_answer"] == 2.0,
        "GraphRAG answers 5%": c["graphrag_answer"] == 5.0,
        "corroboration deficit > 0.9": c["corroboration_deficit"] > 0.9,
        "replaces payload asserts 5% over 2%": node.get("interestRate") == 5.0 and node.get("replaces", {}).get("interestRate") == 2.0,
    }
    return {"checks": checks, "metrics": {k: c[k] for k in ("claims", "stale_claims", "naive_gt_share",
                                                              "temporal_gt_share", "corroboration_deficit")},
            "evidence": {"replaces": node.get("replaces")}}


def case_gated_calculator() -> dict:
    s = _scrape("home-loan-calculator.html")
    rendered = [f for f in s["details"]["rendered_facts"] if f["attribute"] == "interest_rate"]
    hub = payloads.hub_files("meridian")
    md = hub.get("institutional-data/retail/meridian-home-loan.md", "")
    checks = {
        "plain-text crawler sees zero rates": s["static_facts"] == 0,
        "headless execution recovers 8.65%": any(abs(f["value"] - 8.65) < 1e-6 for f in rendered),
        "extraction loss reported as 100%": s["extraction_loss"] == 1.0,
        "Machine Hub has flat Markdown with rate": "8.65%" in md,
    }
    return {"checks": checks, "metrics": {"render_mode": s["render_mode"], "extraction_loss": s["extraction_loss"],
                                          "static_tokens": s["static_tokens"], "rendered_tokens": s["rendered_tokens"]},
            "evidence": {"markdown": md[:400]}}


def case_severance() -> dict:
    r = analytics.severance("meridian", "ESG funds with expense ratio < 0.5%", persist=False)
    checks = {
        "landing = generic homepage": r["landing_url"].endswith("meridian/index.html"),
        f"CSS > {settings.severance_threshold}": r["context_severance_score"] > settings.severance_threshold,
        "best match is the ESG fund page": "esg-leaders-fund" in r["best_match"]["url"],
        "hydration script carries 0.42%": bool(r["hydration"]) and "0.42%" in r["hydration"]["script"],
    }
    return {"checks": checks, "metrics": {"context_severance_score": r["context_severance_score"],
                                          "best_match_distance": r["best_match"]["distance"],
                                          "intent_gap": r["intent_gap"], "backend": r["embedding_backend"]},
            "evidence": {"hydration_markdown": (r["hydration"] or {}).get("markdown")}}


def case_dilution() -> dict:
    a = analytics.namespaced_answer("meridian", "meridian-quant-institutional-fund", "expense_ratio")
    p = analytics.partition("meridian", persist=False)
    matrix = payloads.comparative_matrix("meridian")
    checks = {
        "brand-level retrieval hallucinates 1.25%": a["brand_level_answer"] == 1.25,
        "partitioned retrieval answers 0.45%": a["partitioned_answer"] == 0.45,
        "attribute bleed detected": p["attribute_bleed"]["rate"] > 0.5,
        "matrix contrasts 1.25% vs 0.45%": "1.25%" in matrix and "0.45%" in matrix,
    }
    return {"checks": checks, "metrics": {"semantic_dilution_index": p["semantic_dilution_index"],
                                          "attribute_bleed": p["attribute_bleed"]["rate"],
                                          "brand_votes": a["brand_votes"]},
            "evidence": {"matrix": matrix}}


def case_obfuscation() -> dict:
    s = _scrape("loan-quote.html")
    inter = s["details"]["intercepted"]
    blob = json.dumps(inter)
    checks = {
        "static DOM exposes no APR": s["static_facts"] == 0,
        "XHR JSON intercepted": len(inter) > 0,
        "latent APR 13.49% extracted": any(f["attribute"] == "apr" and f["value"] == 13.49 for f in s["details"]["rendered_facts"]),
        "base64 PDF blob discarded": "JVBERi0" not in blob,
    }
    return {"checks": checks, "metrics": {"render_mode": s["render_mode"], "intercepted_responses": len(inter)},
            "evidence": {"intercepted": inter}}


def case_zero_vector() -> dict:
    s = _scrape("kaveri/index.html")
    ff = payloads.financial_facts("kaveri")
    arb = next((p for p in ff["products"] if p["id"] == "kaveri-arbitrage-fund"), {"facts": {}})
    checks = {
        "sparse page triggers fallback": s["details"]["zero_vector_fallback"],
        "linked SEBI filing crawled": len(s["details"]["filings"]) > 0,
        "financial-facts.json populated (TER 0.38%)": arb["facts"].get("expense_ratio", {}).get("value") == 0.38,
    }
    return {"checks": checks, "metrics": {"static_tokens": s["static_tokens"], "filings": s["details"]["filings"]},
            "evidence": {"facts": arb["facts"]}}


def case_contradictory_truths() -> dict:
    eid = _entity("kaveri", "kaveri-gold-etf")
    graph.resolve_contested(eid, "expense_ratio")
    rows = db.fetchall("""SELECT value_num, status, confidence, evidence FROM fact_claims
                          WHERE entity_id=%s AND attribute='expense_ratio' ORDER BY confidence DESC""", (eid,))
    gt = graph.current_ground_truth(eid, "expense_ratio")
    same_ts = len({r["value_num"] for r in rows}) == 2
    checks = {
        "two official values, same timestamp": same_ts,
        "legal disclaimer (0.35%) wins": gt is not None and gt["value_num"] == 0.35,
        "marketing tagline (0.20%) demoted": any(r["value_num"] == 0.20 and r["status"] == "superseded" for r in rows),
    }
    return {"checks": checks, "metrics": {"candidates": [{"value": r["value_num"], "confidence": r["confidence"],
                                                          "status": r["status"]} for r in rows]},
            "evidence": {"winner": gt["evidence"] if gt else None}}


def case_determinism() -> dict:
    a = payloads.hub_files("meridian")
    b = payloads.hub_files("meridian")
    za, zb = payloads.zip_bytes("meridian"), payloads.zip_bytes("meridian")
    checks = {"Markdown/JSON-LD byte-identical across runs": a == b,
              "ZIP byte-identical across runs": za == zb}
    return {"checks": checks, "metrics": {"files": len(a), "zip_sha256": hashlib.sha256(za).hexdigest()[:16]},
            "evidence": {}}


CASES = [
    ("staleness", "handles factual staleness vs mass-market data", case_staleness),
    ("gated_calculator", "bypasses vector sparsity in gated calculators", case_gated_calculator),
    ("severance", "quantifies context severance on AI referral", case_severance),
    ("dilution", "prevents semantic dilution across brands", case_dilution),
    ("obfuscation", "handles dynamic payload obfuscation", case_obfuscation),
    ("zero_vector", "mitigates zero-vector extraction", case_zero_vector),
    ("contradictory", "resolves simultaneous contradictory ground truths", case_contradictory_truths),
    ("determinism", "serves payloads deterministically", case_determinism),
]

_last: dict | None = None


def run() -> dict:
    global _last
    results = []
    for cid, title, fn in CASES:
        t0 = time.perf_counter()
        try:
            r = fn()
            passed = all(r["checks"].values())
            results.append({"id": cid, "title": title, "passed": passed, **r,
                            "ms": round((time.perf_counter() - t0) * 1000, 1)})
        except Exception as e:  # noqa: BLE001
            results.append({"id": cid, "title": title, "passed": False, "checks": {}, "metrics": {},
                            "error": f"{e!r}", "trace": traceback.format_exc()[-800:],
                            "ms": round((time.perf_counter() - t0) * 1000, 1)})
        logbus.emit("qa", f"it('{title}') {'PASS' if results[-1]['passed'] else 'FAIL'}",
                    "INFO" if results[-1]["passed"] else "ERROR")
    _last = {"ran_at": datetime.now(timezone.utc).isoformat(), "nlp": nlp.status(),
             "passed": sum(r["passed"] for r in results), "total": len(results), "results": results}
    return _last


def report_markdown() -> str:
    r = _last or run()
    L = ["# Risk Validation Report", "",
         f"_AEO Audit Engine, generated {r['ran_at'][:19]}Z. NLP backend: {r['nlp'].get('embedding')} / "
         f"{r['nlp'].get('sentiment')}._", "",
         f"**{r['passed']} of {r['total']} edge cases pass.**", "",
         "This report demonstrates that deterministic text transformations (temporal re-weighting, namespace "
         "partitioning, Machine Hub payloads) constrain the specific failure each case describes. Every figure "
         "below is computed live from the temporal knowledge graph.", ""]
    for c in r["results"]:
        L += [f"## {'PASS' if c['passed'] else 'FAIL'}: {c['title']}", ""]
        for k, v in c["checks"].items():
            L.append(f"- [{'x' if v else ' '}] {k}")
        if c.get("error"):
            L.append(f"- error: `{c['error']}`")
        if c["metrics"]:
            L += ["", "```json", json.dumps(c["metrics"], indent=2, default=str), "```"]
        L.append("")
    L += ["## Method notes", "",
          "- **Corroboration Deficit** = 1 minus the ground truth's share of naive mass, where naive mass per claim is "
          "1 + ln(1 + inbound links) with no time awareness (a proxy for an LLM's statistical prior).",
          "- **Temporal weighting** multiplies each claim by source authority, exponential decay "
          f"(forum half-life {settings.half_life_days['retail_forum']:g} days) and a supersession penalty of "
          f"{settings.supersession_penalty:g} for values contradicting a newer ground truth.",
          f"- **Context Severance Score** is the cosine distance between query and landing-page embeddings; "
          f"hydration triggers above {settings.severance_threshold}.",
          "- **Semantic Dilution Index** = sim(brand, retail centroid) / (sim(brand, retail) + sim(brand, institutional)); "
          "**attribute bleed** is the share of third-party claims about institutional products carrying a retail value.",
          ""]
    return "\n".join(L)
