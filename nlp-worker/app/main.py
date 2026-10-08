"""NLP & Vector Processing Worker (Python / FastAPI).

Sync route handlers run in the threadpool, so the scraper can fetch the worker's own
demo sites while a request is in flight."""
from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import analytics, db, graph, ingest, logbus, nlp, payloads, seed, validation
from .config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
STATE = {"seeding": False, "seed_error": None, "started": time.time()}


def _bootstrap() -> None:
    nlp.load_models()
    logbus.emit("nlp", f"backend ready: {nlp.status()['embedding']} | {nlp.status()['sentiment']}")
    if not settings.seed_on_start or seed.is_seeded():
        return
    STATE["seeding"] = True
    try:
        base = settings.demo_base_url.split("/demo-sites")[0]
        for _ in range(120):          # wait until this server answers, the seed scrapes it over HTTP
            try:
                if httpx.get(base + "/healthz", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
        seed.run()
    except Exception as e:  # noqa: BLE001
        STATE["seed_error"] = repr(e)
        logbus.emit("seed", f"seed failed: {e!r}", "ERROR")
        logging.exception("seed failed")
    finally:
        STATE["seeding"] = False


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_pool()
    threading.Thread(target=_bootstrap, daemon=True).start()
    yield
    db.close_pool()


app = FastAPI(title="AEO Audit Engine: NLP Worker", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/demo-sites", StaticFiles(directory=Path(__file__).parent / "demo_sites", html=True), name="demo")


@app.exception_handler(KeyError)
async def _key(_, e: KeyError):
    return JSONResponse({"detail": str(e).strip("'")}, status_code=404)


@app.exception_handler(ValueError)
async def _val(_, e: ValueError):
    return JSONResponse({"detail": str(e)}, status_code=422)


# ------------------------------------------------------------------ meta

@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/health")
def health():
    return {"status": "seeding" if STATE["seeding"] else "ready", "seed_error": STATE["seed_error"],
            "nlp": nlp.status(), "uptime_s": round(time.time() - STATE["started"]),
            "severance_threshold": settings.severance_threshold}


@app.get("/api/logs")
def logs(after_id: int = 0, limit: int = Query(200, le=500)):
    return logbus.since(after_id, limit)


@app.post("/api/admin/reseed")
def reseed():
    return seed.run(force=True)


# ------------------------------------------------------------------ institutions / explorer

@app.get("/api/institutions")
def institutions():
    return db.fetchall(
        """SELECT i.slug, i.name, i.domain, i.homepage,
                  (SELECT count(*) FROM entity_nodes e WHERE e.institution_id=i.id) AS entities,
                  (SELECT count(*) FROM pages p WHERE p.institution_id=i.id) AS pages
           FROM institutions i ORDER BY i.name""")


@app.get("/api/institutions/{slug}/entities")
def entities(slug: str):
    ingest.institution(slug)
    rows = db.fetchall(
        """SELECT en.id, en.slug, en.entity_name, en.namespace_type, en.entity_kind, en.aliases, en.descriptors,
                  (SELECT count(*) FROM fact_claims fc WHERE fc.entity_id=en.id) AS claims,
                  (SELECT count(*) FROM temporal_embeddings te WHERE te.entity_id=en.id) AS text_nodes,
                  (SELECT array_agg(DISTINCT attribute) FROM fact_claims fc WHERE fc.entity_id=en.id) AS attributes
           FROM entity_nodes en JOIN institutions i ON i.id=en.institution_id
           WHERE i.slug=%s ORDER BY en.namespace_type DESC, en.entity_kind, en.entity_name""", (slug,))
    for r in rows:
        r["id"] = str(r["id"])
        r["attributes"] = sorted(a for a in (r["attributes"] or []) if a)
    return rows


@app.get("/api/institutions/{slug}/overview")
def overview(slug: str):
    inst = ingest.institution(slug)
    iid = inst["id"]
    sc = db.fetchone("""SELECT avg(extraction_loss) AS loss, count(*) AS n, sum(static_facts) AS sf,
                               sum(rendered_facts) AS rf FROM (SELECT DISTINCT ON (url) * FROM scrape_logs
                        WHERE institution_id=%s ORDER BY url, fetched_at DESC) s""", (iid,))
    co = db.fetchall("""SELECT DISTINCT ON (c.entity_id, c.attribute) c.*, en.entity_name FROM corroboration_logs c
                        JOIN entity_nodes en ON en.id=c.entity_id WHERE en.institution_id=%s
                        ORDER BY c.entity_id, c.attribute, c.computed_at DESC""", (iid,))
    sv = db.fetchall("""SELECT query, severance_score, hydrate, best_match_url, created_at FROM severance_runs
                        WHERE institution_id=%s ORDER BY created_at DESC LIMIT 12""", (iid,))
    dl = db.fetchone("SELECT * FROM dilution_runs WHERE institution_id=%s ORDER BY created_at DESC LIMIT 1", (iid,))
    counts = db.fetchone("""SELECT (SELECT count(*) FROM temporal_embeddings te JOIN entity_nodes en ON en.id=te.entity_id
                                    WHERE en.institution_id=%(i)s) AS text_nodes,
                                   (SELECT count(*) FROM fact_claims fc JOIN entity_nodes en ON en.id=fc.entity_id
                                    WHERE en.institution_id=%(i)s) AS claims""", {"i": iid})
    return {
        "institution": {"slug": inst["slug"], "name": inst["name"], "domain": inst["domain"]},
        "counts": counts,
        "sparsity": {"pages": sc["n"], "avg_extraction_loss": round(sc["loss"] or 0, 4),
                     "static_facts": sc["sf"] or 0, "rendered_facts": sc["rf"] or 0},
        "staleness": [{"entity": r["entity_name"], "entity_id": str(r["entity_id"]), "attribute": r["attribute"],
                       "ground_truth": r["ground_truth_value"], "corroboration_deficit": r["corroboration_deficit"],
                       "naive_share": r["naive_gt_share"], "temporal_share": r["temporal_gt_share"],
                       "stale_claims": r["stale_claims"], "naive_answer": (r["details"] or {}).get("naive_answer"),
                       "graph_answer": (r["details"] or {}).get("graph_answer")} for r in co],
        "severance": sv,
        "dilution": None if not dl else {"index": dl["dilution_index"], "attribute_bleed": dl["attribute_bleed"],
                                         "details": dl["details"]},
    }


# ------------------------------------------------------------------ Problem 1: sparsity

class ScrapeReq(BaseModel):
    institution: str
    url: str
    namespace: str | None = None
    entity: str | None = None
    landing: bool = False


@app.post("/api/scrape")
def scrape(req: ScrapeReq):
    return ingest.scrape_and_ingest(req.institution, req.url, req.namespace, req.entity, req.landing)


@app.get("/api/institutions/{slug}/scrapes")
def scrapes(slug: str):
    inst = ingest.institution(slug)
    rows = db.fetchall("""SELECT DISTINCT ON (url) id, url, fetched_at, render_mode, static_tokens, rendered_tokens,
                                 static_facts, rendered_facts, extraction_loss, details
                          FROM scrape_logs WHERE institution_id=%s ORDER BY url, fetched_at DESC""", (inst["id"],))
    for r in rows:
        r["id"] = str(r["id"])
    return sorted(rows, key=lambda r: -(r["extraction_loss"] or 0))


# ------------------------------------------------------------------ Problem 2: staleness

class TextReq(BaseModel):
    institution: str
    entity: str | None = None
    text: str = Field(min_length=3)
    source_type: str = "retail_forum"
    source_url: str | None = None
    observed_at: datetime | None = None
    link_count: int = 0


@app.post("/api/ingest/text")
def ingest_text(req: TextReq):
    if req.source_type not in settings.authority:
        raise HTTPException(422, f"source_type must be one of {sorted(settings.authority)}")
    return ingest.ingest_text(req.institution, req.entity, req.text, req.source_type, req.source_url,
                              req.observed_at or graph.now(), req.link_count)


@app.get("/api/entities/{entity_id}/corroboration")
def corroboration(entity_id: str, attribute: str):
    return graph.corroboration(entity_id, attribute)


@app.get("/api/entities/{entity_id}/graph")
def entity_graph(entity_id: str, attribute: str):
    return graph.graph_view(entity_id, attribute)


@app.get("/api/entities/{entity_id}/texts")
def entity_texts(entity_id: str, limit: int = 30):
    rows = db.fetchall("""SELECT content, source_type, source_url, valid_from, valid_to, link_count, sentiment
                          FROM temporal_embeddings WHERE entity_id=%s ORDER BY link_count DESC, valid_from DESC LIMIT %s""",
                       (entity_id, limit))
    return rows


# ------------------------------------------------------------------ Problem 3: severance

class SeveranceReq(BaseModel):
    institution: str
    query: str = Field(min_length=3)
    landing_url: str | None = None


@app.post("/api/severance")
def severance(req: SeveranceReq):
    return analytics.severance(req.institution, req.query, req.landing_url)


@app.get("/api/institutions/{slug}/severance")
def severance_history(slug: str):
    inst = ingest.institution(slug)
    return db.fetchall("""SELECT query, landing_url, cosine_distance, severance_score, best_match_url, hydrate, created_at
                          FROM severance_runs WHERE institution_id=%s ORDER BY created_at DESC LIMIT 50""", (inst["id"],))


# ------------------------------------------------------------------ Problem 4: dilution

@app.post("/api/institutions/{slug}/partition")
def partition(slug: str):
    ingest.institution(slug)
    return analytics.partition(slug)


@app.get("/api/institutions/{slug}/namespaced-answer")
def namespaced_answer(slug: str, entity: str, attribute: str):
    return analytics.namespaced_answer(slug, entity, attribute)


# ------------------------------------------------------------------ payloads / machine hub

@app.get("/api/hubs/{slug}/manifest")
def hub_manifest(slug: str):
    ingest.institution(slug)
    return payloads.manifest(slug)


@app.get("/api/hubs/{slug}/financial-facts.json")
def hub_facts(slug: str):
    return payloads.financial_facts(slug)


@app.get("/api/hubs/{slug}/schema.jsonld")
def hub_schema(slug: str):
    return Response(payloads.hub_files(slug)["schema.jsonld"], media_type="application/ld+json")


@app.get("/api/hubs/{slug}/file", response_class=PlainTextResponse)
def hub_file(slug: str, path: str):
    files = payloads.hub_files(slug)
    if path not in files:
        raise HTTPException(404, "no such hub file")
    return files[path]


@app.get("/api/hubs/{slug}/institutional-data/{path:path}", response_class=PlainTextResponse)
def hub_markdown(slug: str, path: str = ""):
    files = payloads.hub_files(slug)
    key = "institutional-data/" + (path or "index.md")
    if key not in files:
        raise HTTPException(404, "no such hub file")
    return Response(files[key], media_type="text/markdown; charset=utf-8")


@app.get("/api/hubs/{slug}/hydration.js")
def hydration(slug: str, query: str):
    r = analytics.severance(slug, query, persist=False)
    h = r["hydration"] or analytics.hydration_payload(slug, query, r["best_match"]["url"])
    return Response(h["script"], media_type="application/javascript")


@app.get("/api/hubs/{slug}/export.zip")
def hub_zip(slug: str):
    ingest.institution(slug)
    extra = {"risk-validation-report.md": validation.report_markdown()}
    return Response(payloads.zip_bytes(slug, extra), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{slug}-machine-hub.zip"'})


# ------------------------------------------------------------------ NLP utilities

class AnalyseReq(BaseModel):
    text: str = Field(min_length=1)


@app.post("/api/nlp/analyse")
def analyse(req: AnalyseReq):
    return nlp.analyse(req.text)


# ------------------------------------------------------------------ QA / validation

@app.post("/api/validation/run")
def run_validation():
    return validation.run()


@app.get("/api/validation/report.md")
def validation_report():
    return Response(validation.report_markdown(), media_type="text/markdown; charset=utf-8")
