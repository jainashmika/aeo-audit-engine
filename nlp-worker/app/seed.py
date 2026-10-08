"""Seeded demo: two fictional institutions whose public footprint reproduces every
edge case in the QA specification. Runs once against an empty database."""
from __future__ import annotations

import random
import uuid
from datetime import timedelta

from . import analytics, db, graph, ingest, logbus, nlp
from .config import settings

INSTITUTIONS = {
    "meridian": {"name": "Meridian Bank", "domain": "meridian.example", "home": "meridian/index.html"},
    "kaveri": {"name": "Kaveri Capital", "domain": "kaveri.example", "home": "kaveri/index.html"},
}

ENTITIES = [
    # (inst, slug, name, namespace, kind, aliases, descriptors, replaces)
    ("meridian", "meridian-retail-banking", "Meridian Retail Banking", "Retail", "division", ["Meridian Bank retail"],
     {"audience": "Mass Market", "support": "Branch network & call centre", "fees": "Regular plan, distributor commission",
      "flagship": "meridian-retail-equity-fund"}, None),
    ("meridian", "meridian-quant", "Meridian Quant Asset Management", "Institutional", "division", ["Meridian Quant"],
     {"audience": "High-Net-Worth / Corporate", "support": "Dedicated relationship manager",
      "fees": "Institutional share class, no commission", "flagship": "meridian-quant-institutional-fund"}, None),
    ("meridian", "meridian-savings", "Meridian Savings Account", "Retail", "product", ["savings account"], {}, None),
    ("meridian", "meridian-nifty-dividend-etf", "Meridian Nifty Dividend ETF", "Retail", "product",
     ["MERDIVETF", "Meridian dividend ETF", "Meridian Nifty Dividend"], {}, None),
    ("meridian", "meridian-home-loan", "Meridian Home Loan", "Retail", "product", ["Meridian mortgage"], {}, None),
    ("meridian", "meridian-home-loan-bt", "Meridian Home Loan Balance Transfer", "Retail", "product", [], {}, None),
    ("meridian", "meridian-personal-loan", "Meridian Personal Loan", "Retail", "product", [], {}, None),
    ("meridian", "meridian-esg-leaders-fund", "Meridian ESG Leaders Fund", "Retail", "product", ["Meridian ESG fund"], {}, None),
    ("meridian", "meridian-retail-equity-fund", "Meridian Retail Equity Fund", "Retail", "product", [], {}, None),
    ("meridian", "meridian-retirement-advantage", "Meridian Retirement Advantage Account", "Retail", "product", [], {}, None),
    ("meridian", "meridian-quant-institutional-fund", "Meridian Quant Institutional Fund", "Institutional", "product",
     ["Meridian Quant fund"], {}, None),
    ("meridian", "legacy-yield-fund", "Legacy Yield Fund", "Retail", "product", [], {"status": "discontinued"}, None),
    ("meridian", "premium-institutional-yield-fund", "Premium Institutional Yield Fund", "Institutional", "product",
     [], {}, "legacy-yield-fund"),
    ("kaveri", "kaveri-arbitrage-fund", "Kaveri Arbitrage Fund", "Institutional", "product", [], {}, None),
    ("kaveri", "kaveri-gold-etf", "Kaveri Gold ETF", "Institutional", "product", [], {}, None),
]

# (inst, path, namespace, entity, landing, days_ago)
PAGES = [
    ("meridian", "meridian/funds/legacy-yield-fund.html", "Retail", "legacy-yield-fund", False, 700),
    ("meridian", "meridian/index.html", "Retail", "meridian-savings", True, 2),
    ("meridian", "meridian/etf/nifty-dividend-etf.html", "Retail", "meridian-nifty-dividend-etf", False, 1),
    ("meridian", "meridian/loans/home-loan-calculator.html", "Retail", "meridian-home-loan", False, 1),
    ("meridian", "meridian/loans/loan-quote.html", "Retail", "meridian-personal-loan", False, 1),
    ("meridian", "meridian/funds/esg-leaders-fund.html", "Retail", "meridian-esg-leaders-fund", False, 3),
    ("meridian", "meridian/funds/retail-equity-fund.html", "Retail", "meridian-retail-equity-fund", False, 30),
    ("meridian", "meridian/retirement/retirement-advantage.html", "Retail", "meridian-retirement-advantage", False, 20),
    ("meridian", "meridian/quant/index.html", "Institutional", "meridian-quant-institutional-fund", False, 5),
    ("meridian", "meridian/funds/premium-institutional-yield-fund.html", "Institutional",
     "premium-institutional-yield-fund", False, 0),
    ("kaveri", "kaveri/index.html", "Institutional", "kaveri-arbitrage-fund", True, 2),
    ("kaveri", "kaveri/etf/kaveri-gold-etf.html", "Institutional", "kaveri-gold-etf", False, 1),
]

ETF_STALE = [
    "Meridian Nifty Dividend ETF yields about 2% so honestly not worth it vs FDs.",
    "MERDIVETF dividend yield is 2% last I checked, decent for a passive income core.",
    "Holding Meridian Nifty Dividend ETF for 2 years, yield of 2.0% but steady.",
    "Why does everyone hype the Meridian Nifty Dividend ETF? A 2% yield is meh.",
    "PSA: Meridian Nifty Dividend ETF pays roughly 2% yield, don't expect income miracles.",
    "Compared ETFs: Meridian Nifty Dividend ETF yield 2%, expense is fine though.",
    "My dad bought Meridian Nifty Dividend ETF for the 2% yield, I told him to look elsewhere.",
    "Is 2% yield on Meridian Nifty Dividend ETF good for a retiree? Feels low.",
    "Meridian Nifty Dividend ETF: 2% dividend yield, low tracking error, boring but works.",
    "Switched out of Meridian Nifty Dividend ETF, the 2% yield just wasn't enough.",
    "Anyone know if the Meridian Nifty Dividend ETF yield is still 2%? Thinking of SIPs.",
    "Meridian Nifty Dividend ETF review: yield 2.00%, liquidity ok on NSE.",
]
ETF_FRESH = [
    "Wow, Meridian Nifty Dividend ETF yield is 5% now after the rebalance?",
    "Just saw Meridian Nifty Dividend ETF distribution yield updated to 5.00%.",
]
QUANT_BLEED = [
    "Meridian Quant Institutional Fund probably charges the same 1.25% expense ratio as their branch funds.",
    "Heard the Meridian Quant Institutional Fund has a 1.25% expense ratio, typical bank fees.",
    "Meridian is a retail bank, their Meridian Quant Institutional Fund will have 1.25% expense ratio like everything else.",
    "Meridian Quant Institutional Fund expense ratio is 1.25%? Avoid, bank products are overpriced.",
]
QUANT_OK = ["Meridian Quant Institutional Fund institutional class expense ratio is 0.45%, quite reasonable."]
BRAND_RETAIL = [
    "Meridian Bank branch queues are long but staff is friendly, savings account works fine.",
    "Meridian credit card rewards are ok for groceries, customer care helpline is slow.",
    "Meridian is a mass market bank, good for everyday banking, nothing premium.",
    "Got a personal loan from Meridian branch, approval was quick, fees were hidden.",
]
PRESS = [
    "Meridian Nifty Dividend ETF offers a dividend yield of 2.00%, according to the fund house.",
    "Income investors note the Meridian Nifty Dividend ETF yield of 2% trails peers.",
]


def _url(path: str) -> str:
    return f"{settings.demo_base_url.rstrip('/')}/{path}"


def is_seeded() -> bool:
    r = db.fetchone("SELECT count(*) AS n FROM institutions")
    return bool(r and r["n"])


def reset() -> None:
    db.execute("""TRUNCATE institutions, entity_nodes, temporal_embeddings, fact_claims, graph_edges,
                  corroboration_logs, pages, scrape_logs, severance_runs, dilution_runs, audit_log CASCADE""")


def _bulk_forum(slug: str, entity_slug: str, templates: list[str], n: int, start_days: int, end_days: int,
                source_type: str, rng: random.Random, namespace: str = "Retail", link_scale: float = 1.0) -> int:
    inst = ingest.institution(slug)
    ent = db.fetchone("SELECT id FROM entity_nodes WHERE institution_id=%s AND slug=%s", (inst["id"], entity_slug))
    eid = str(ent["id"]) if ent else None
    now = graph.now()
    vecs = dict(zip(templates, nlp.embed_many(templates)))
    tmpl_facts = {}
    for t in templates:
        fs = []
        for f in nlp.extract_facts(t):
            fe = graph.resolve_entity(str(inst["id"]), f.product_hint, eid)
            if fe:
                fs.append((fe, f))
        tmpl_facts[t] = fs
    sents = {t: nlp.sentiment(t) for t in templates}
    te_rows, fc_rows = [], []
    for i in range(n):
        t = templates[rng.randrange(len(templates))]
        # beta(2,3) skews toward the older half of the window, like real forum archives
        frac = rng.betavariate(2, 3)
        ts = now - timedelta(days=start_days - frac * (start_days - end_days), minutes=rng.randrange(1440))
        links = int(min(rng.paretovariate(1.3) * link_scale, 5000)) - 1
        sid = str(uuid.uuid4())
        host = "reddit.com/r/IndiaInvestments" if source_type == "retail_forum" else "news.example"
        te_rows.append((sid, eid, db.vec(vecs[t]), ts, source_type, f"https://{host}/p/{i}", namespace, t,
                        nlp.content_hash(t), settings.authority[source_type], links, db.jsonb(sents[t])))
        for fe, f in tmpl_facts[t]:
            fc_rows.append((str(uuid.uuid4()), fe, sid, f.attribute, f.value, f.unit, source_type,
                            f"https://{host}/p/{i}", ts, ts, links, settings.authority[source_type],
                            f.confidence, f.sentence))
    with db.conn() as c:
        with c.cursor() as cur:
            cur.executemany(
                """INSERT INTO temporal_embeddings(id,entity_id,embedding,valid_from,source_type,source_url,namespace_type,
                       content,content_hash,authority,link_count,sentiment) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                te_rows)
            cur.executemany(
                """INSERT INTO fact_claims(id,entity_id,embedding_id,attribute,value_num,unit,source_type,source_url,
                       observed_at,valid_from,link_count,authority,confidence,evidence)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", fc_rows)
    return n


def run(force: bool = False) -> dict:
    if is_seeded() and not force:
        return {"seeded": False, "reason": "already seeded"}
    reset()
    logbus.emit("seed", "seeding demo institutions (Meridian Bank, Kaveri Capital)")
    rng = random.Random(42)
    ids = {s: graph.upsert_institution(s, v["name"], v["domain"], _url(v["home"])) for s, v in INSTITUTIONS.items()}
    slug_to_id: dict[tuple, str] = {}
    for inst, slug, name, ns, kind, aliases, desc, repl in ENTITIES:
        rid = slug_to_id.get((inst, repl)) if repl else None
        slug_to_id[(inst, slug)] = graph.upsert_entity(ids[inst], slug, name, ns, kind, aliases, desc, rid)
    now = graph.now()

    # official history: the ETF page said 2.00% from 2022 until yesterday's update
    ingest.ingest_text("meridian", "meridian-nifty-dividend-etf",
                       "Meridian Nifty Dividend ETF distribution yield is 2.00% per annum as per the Scheme Information Document.",
                       "institutional_web", _url("meridian/etf/nifty-dividend-etf.html") + "#archive-2022",
                       now - timedelta(days=1650), link_count=40)

    for inst, path, ns, ent, landing, days in PAGES:
        ingest.scrape_and_ingest(inst, _url(path), ns, ent, landing, now - timedelta(days=days))

    n = 0
    n += _bulk_forum("meridian", "meridian-nifty-dividend-etf", ETF_STALE, 10_000, 1640, 3, "retail_forum", rng)
    n += _bulk_forum("meridian", "meridian-nifty-dividend-etf", PRESS, 30, 1500, 200, "press", rng, link_scale=20)
    n += _bulk_forum("meridian", "meridian-nifty-dividend-etf", ETF_FRESH, 12, 1, 0, "retail_forum", rng)
    n += _bulk_forum("meridian", "meridian-quant-institutional-fund", QUANT_BLEED, 1_400, 700, 2, "retail_forum",
                     rng, namespace=None)
    n += _bulk_forum("meridian", "meridian-quant-institutional-fund", QUANT_OK, 40, 60, 1, "retail_forum", rng,
                     namespace=None)
    n += _bulk_forum("meridian", "meridian-retail-banking", BRAND_RETAIL, 3_000, 1800, 1, "retail_forum", rng)
    logbus.emit("seed", f"ingested {n:,} third-party text nodes (forums, press)")

    # first analytic passes so the dashboard opens with history
    for slug, attr in [("meridian-nifty-dividend-etf", "yield"), ("meridian-quant-institutional-fund", "expense_ratio"),
                       ("kaveri-gold-etf", "expense_ratio")]:
        inst = "kaveri" if slug.startswith("kaveri") else "meridian"
        graph.corroboration(slug_to_id[(inst, slug)], attr)
    for q in ["ESG funds with expense ratio < 0.5%", "tax-advantaged retirement accounts in India",
              "home loan interest rate Meridian", "institutional quant mandate for corporate treasury"]:
        analytics.severance("meridian", q)
    analytics.partition("meridian")
    analytics.partition("kaveri")
    logbus.emit("seed", "demo ready")
    return {"seeded": True, "third_party_nodes": n}
