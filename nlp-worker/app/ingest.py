"""Ingestion: page scrapes and unstructured text -> temporal graph."""
from __future__ import annotations

from datetime import datetime

from . import db, graph, logbus, nlp, scraper


def institution(slug: str) -> dict:
    row = db.fetchone("SELECT * FROM institutions WHERE slug=%s", (slug,))
    if not row:
        raise KeyError(f"unknown institution {slug}")
    return row


def scrape_and_ingest(slug: str, url: str, namespace: str | None = None, entity_slug: str | None = None,
                      is_landing: bool = False, observed_at: datetime | None = None,
                      source_type: str = "institutional_web") -> dict:
    inst = institution(slug)
    iid = str(inst["id"])
    observed_at = observed_at or graph.now()
    logbus.emit("scraper", f"GET {url}", institution=slug)
    view = scraper.fetch_view(url)
    rep = scraper.extraction_loss(view)
    default_entity = None
    if entity_slug:
        e = db.fetchone("SELECT id FROM entity_nodes WHERE institution_id=%s AND slug=%s", (iid, entity_slug))
        default_entity = str(e["id"]) if e else None

    page_vec = nlp.embed(view.rendered_text or view.static_text or view.title)
    db.execute(
        """INSERT INTO pages(institution_id,url,title,namespace_type,is_landing,static_text,rendered_text,embedding,fetched_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (url) DO UPDATE SET title=EXCLUDED.title, namespace_type=COALESCE(EXCLUDED.namespace_type,pages.namespace_type),
             is_landing=EXCLUDED.is_landing OR pages.is_landing, static_text=EXCLUDED.static_text,
             rendered_text=EXCLUDED.rendered_text, embedding=EXCLUDED.embedding, fetched_at=EXCLUDED.fetched_at""",
        (iid, url, view.title, namespace, is_landing, view.static_text, view.rendered_text, db.vec(page_vec), observed_at))

    claims = []
    emb_id = None
    if default_entity:
        emb_id = graph.add_text(default_entity, view.rendered_text[:8000], source_type, url, observed_at,
                                namespace=namespace, vector=page_vec, sentiment=nlp.sentiment(view.rendered_text[:1500]))
    for f in rep.rendered_facts:
        eid = graph.resolve_entity(iid, f.product_hint, default_entity)
        if not eid:
            continue
        claims.append(graph.add_claim(eid, f.attribute, f.value, f.unit, source_type, url, observed_at,
                                      link_count=1, confidence=f.confidence, evidence=f.sentence, embedding_id=emb_id))
    for filing in view.filings:
        for f in nlp.extract_facts(filing["text"]):
            eid = graph.resolve_entity(iid, f.product_hint, default_entity)
            if eid:
                claims.append(graph.add_claim(eid, f.attribute, f.value, f.unit, "institutional_filing",
                                              filing["url"], observed_at, link_count=1, confidence=f.confidence,
                                              evidence=f.sentence))
        if default_entity:
            graph.add_text(default_entity, filing["text"][:8000], "institutional_filing", filing["url"], observed_at,
                           namespace=namespace)

    details = {
        "title": view.title, "lost_facts": [f.__dict__ for f in rep.lost],
        "static_facts": [f.__dict__ for f in rep.static_facts],
        "rendered_facts": [f.__dict__ for f in rep.rendered_facts],
        "filing_facts": [f.__dict__ for f in rep.filing_facts],
        "intercepted": [{"url": c["url"], "json": c["json"]} for c in view.intercepted],
        "filings": [{"url": f["url"], "chars": len(f["text"])} for f in view.filings],
        "token_loss": rep.token_loss,
        "static_excerpt": view.static_text[:1200], "rendered_excerpt": view.rendered_text[:1600],
        "zero_vector_fallback": bool(view.filings),
    }
    row = db.fetchone(
        """INSERT INTO scrape_logs(institution_id,url,render_mode,static_tokens,rendered_tokens,static_facts,
               rendered_facts,extraction_loss,details,fetched_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (iid, url, view.render_mode, rep.static_tokens, rep.rendered_tokens, len(rep.static_facts),
         len(rep.rendered_facts) + len(rep.filing_facts), rep.extraction_loss, db.jsonb(details), observed_at))
    lvl = "WARN" if rep.extraction_loss > 0.5 else "INFO"
    logbus.emit("scraper", f"{view.render_mode}: extraction loss {rep.extraction_loss:.0%} "
                f"({len(rep.static_facts)} static vs {len(rep.rendered_facts) + len(rep.filing_facts)} rendered facts)"
                + (" | zero-vector fallback crawled filings" if view.filings else ""), lvl, url=url)
    return {"scrape_id": str(row["id"]), "url": url, "render_mode": view.render_mode,
            "extraction_loss": rep.extraction_loss, "token_loss": rep.token_loss,
            "static_tokens": rep.static_tokens, "rendered_tokens": rep.rendered_tokens,
            "claims_created": len(claims), **details}


def ingest_text(slug: str, entity_slug: str | None, text: str, source_type: str, source_url: str | None,
                observed_at: datetime, link_count: int = 0, namespace: str | None = None,
                vector=None, quiet: bool = False) -> dict:
    inst = institution(slug)
    iid = str(inst["id"])
    default_entity = None
    if entity_slug:
        e = db.fetchone("SELECT id FROM entity_nodes WHERE institution_id=%s AND slug=%s", (iid, entity_slug))
        default_entity = str(e["id"]) if e else None
    sent = nlp.sentiment(text)
    emb_id = graph.add_text(default_entity, text, source_type, source_url, observed_at, link_count,
                            namespace, vector=vector, sentiment=sent)
    claims = []
    for f in nlp.extract_facts(text):
        eid = graph.resolve_entity(iid, f.product_hint, default_entity)
        if eid:
            claims.append(graph.add_claim(eid, f.attribute, f.value, f.unit, source_type, source_url, observed_at,
                                          link_count, f.confidence, f.sentence, emb_id))
    if not quiet:
        logbus.emit("ingest", f"{source_type} text -> {len(claims)} claims", institution=slug)
    return {"embedding_id": emb_id, "claims": claims, "sentiment": sent}
