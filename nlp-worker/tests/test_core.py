"""Unit tests (no database) plus an integration test that runs the edge-case suite
against a seeded database when one is reachable."""
import os

import numpy as np
import pytest

from app import graph, nlp, payloads


def test_extracts_percent_facts_with_attributes():
    fs = nlp.extract_facts("The Meridian ESG Leaders Fund has a total expense ratio of 0.42% per annum, well below 0.5%.")
    assert [(f.attribute, f.value) for f in fs] == [("expense_ratio", 0.42)]
    assert fs[0].product_hint == "Meridian ESG Leaders Fund"


def test_nearest_keyword_wins_inside_a_sentence():
    fs = nlp.extract_facts("Interest rate from 8.65% p.a. Processing fee 0.5%.")
    got = {(f.attribute, f.value) for f in fs}
    assert ("interest_rate", 8.65) in got and ("processing_fee", 0.5) in got
    assert ("interest_rate", 0.5) not in got


def test_inr_minimums():
    fs = nlp.extract_facts("Minimum investment: ₹10 crore per mandate.")
    assert fs[0].attribute == "min_investment" and fs[0].value == 1e8


def test_json_interception_facts():
    obj = {"pdf_base64": "JVBERi0xLjQ=", "quote": {"product": "Meridian Personal Loan", "apr": 13.49}}
    fs = nlp.facts_from_json(obj)
    assert [(f.attribute, f.value, f.product_hint) for f in fs] == [("apr", 13.49, "Meridian Personal Loan")]


def test_lite_embedding_is_deterministic_and_normalised():
    a, b = nlp.lite_embed("ESG funds with expense ratio < 0.5%"), nlp.lite_embed("ESG funds with expense ratio < 0.5%")
    assert np.array_equal(a, b) and abs(np.linalg.norm(a) - 1) < 1e-5 and a.shape == (768,)
    assert nlp.cosine(a, nlp.lite_embed("sustainable fund low TER")) > nlp.cosine(a, nlp.lite_embed("credit card rewards"))


def test_legal_syntax_beats_marketing():
    marketing = "Introducing the new Kaveri Gold ETF, now with an incredible 0.20% expense ratio!"
    legal = "Total expense ratio of Kaveri Gold ETF is 0.35% per annum w.e.f. 01-Oct-2026 as per the Scheme Information Document."
    assert nlp.legal_syntax_score(legal) > nlp.legal_syntax_score(marketing)


def test_decay_and_naive_weight():
    assert graph.decay(90, 90) == pytest.approx(0.5)
    assert graph.decay(10, None) == 1.0
    assert graph.naive_weight(0) == 1.0 and graph.naive_weight(100) > graph.naive_weight(10)


def test_hydration_script_only_fires_for_ai_referrers():
    js = payloads.hydration_script("ESG funds", "ESG Leaders", "https://x/esg",
                                   [{"entity": "ESG Fund", "attribute": "expense_ratio", "display": "0.42%",
                                     "valid_from": "2026-10-01T00:00:00Z"}])
    assert "chatgpt" in js and "0.42%" in js and js == payloads.hydration_script(
        "ESG funds", "ESG Leaders", "https://x/esg",
        [{"entity": "ESG Fund", "attribute": "expense_ratio", "display": "0.42%", "valid_from": "2026-10-01T00:00:00Z"}])


def _db_ready() -> bool:
    try:
        import psycopg
        with psycopg.connect(os.getenv("DATABASE_URL", "postgresql://aeo:aeo@localhost:5432/aeo"), connect_timeout=2) as c:
            return bool(c.execute("SELECT count(*) FROM institutions").fetchone()[0])
    except Exception:
        return False


@pytest.mark.skipif(not _db_ready(), reason="needs a seeded PostgreSQL (docker compose up)")
def test_edge_case_suite_against_seeded_db():
    from app import db, validation
    db.init_pool()
    try:
        res = validation.run()
        failed = [r["title"] for r in res["results"] if not r["passed"]]
        assert not failed, failed
    finally:
        db.close_pool()
