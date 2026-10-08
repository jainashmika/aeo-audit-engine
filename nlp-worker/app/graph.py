"""Temporal Knowledge Graph + Corroboration Deficit (Req 2.1, 2.2).

Nodes  : entity_nodes, temporal_embeddings (text with valid_from/valid_to), fact_claims
Edges  : SUPERSEDES (new ground truth -> old), CONTRADICTS (stale claim -> ground truth),
         SUPPORTS (claim -> ground truth)

The Corroboration Deficit measures how badly the open-web corpus outvotes the current
ground truth when weighted the way an LLM's statistical prior weights it (volume x links,
no notion of time). The temporal re-weighting then applies authority, timestamp decay
and a supersession penalty so that older heavily-linked forum data can no longer
overwrite newer sparsely-linked filings.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from . import db, logbus, nlp
from .config import INSTITUTIONAL_SOURCES, settings


def now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ writes

def upsert_institution(slug: str, name: str, domain: str, homepage: str) -> str:
    row = db.fetchone(
        """INSERT INTO institutions(slug,name,domain,homepage) VALUES (%s,%s,%s,%s)
           ON CONFLICT (slug) DO UPDATE SET name=EXCLUDED.name, domain=EXCLUDED.domain, homepage=EXCLUDED.homepage
           RETURNING id""", (slug, name, domain, homepage))
    return str(row["id"])


def upsert_entity(institution_id: str, slug: str, name: str, namespace: str, kind: str = "product",
                  aliases: list[str] | None = None, descriptors: dict | None = None,
                  replaces: str | None = None) -> str:
    row = db.fetchone(
        """INSERT INTO entity_nodes(institution_id,slug,entity_name,namespace_type,entity_kind,aliases,descriptors,replaces_entity)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (institution_id,slug) DO UPDATE SET entity_name=EXCLUDED.entity_name,
             namespace_type=EXCLUDED.namespace_type, entity_kind=EXCLUDED.entity_kind, aliases=EXCLUDED.aliases,
             descriptors=EXCLUDED.descriptors, replaces_entity=COALESCE(EXCLUDED.replaces_entity, entity_nodes.replaces_entity)
           RETURNING id""",
        (institution_id, slug, name, namespace, kind, aliases or [], db.jsonb(descriptors or {}), replaces))
    return str(row["id"])


def add_text(entity_id: str | None, text: str, source_type: str, source_url: str | None,
             observed_at: datetime, link_count: int = 0, namespace: str | None = None,
             vector=None, sentiment: dict | None = None) -> str:
    v = vector if vector is not None else nlp.embed(text)
    row = db.fetchone(
        """INSERT INTO temporal_embeddings(entity_id,embedding,valid_from,source_type,source_url,namespace_type,
                 content,content_hash,authority,link_count,sentiment)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (entity_id, db.vec(v), observed_at, source_type, source_url, namespace, text,
         nlp.content_hash(text), settings.authority.get(source_type, 0.5), link_count,
         db.jsonb(sentiment) if sentiment else None))
    return str(row["id"])


def add_claim(entity_id: str, attribute: str, value: float, unit: str, source_type: str,
              source_url: str | None, observed_at: datetime, link_count: int = 0,
              confidence: float = 0.5, evidence: str | None = None, embedding_id: str | None = None) -> str:
    """Insert a claim. Institutional claims become ground truth and supersede the prior version."""
    is_gt = source_type in INSTITUTIONAL_SOURCES
    cid = str(uuid.uuid4())
    with db.conn() as c:
        prior = None
        if is_gt:
            # Simultaneous contradictory ground truths are resolved separately (tie-breaker)
            prior = c.execute(
                """SELECT id, value_num, valid_from FROM fact_claims
                   WHERE entity_id=%s AND attribute=%s AND is_ground_truth AND valid_to IS NULL
                   ORDER BY valid_from DESC LIMIT 1""", (entity_id, attribute)).fetchone()
            if prior and prior["valid_from"] > observed_at:
                is_gt = False  # older official statement arriving late: historical, not current
                prior = None
        c.execute(
            """INSERT INTO fact_claims(id,entity_id,embedding_id,attribute,value_num,unit,source_type,source_url,
                    observed_at,valid_from,link_count,authority,confidence,is_ground_truth,evidence,supersedes,status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (cid, entity_id, embedding_id, attribute, value, unit, source_type, source_url, observed_at,
             observed_at, link_count, settings.authority.get(source_type, 0.5), confidence, is_gt, evidence,
             None, "active"))
        if prior and is_gt:
            same_instant = abs((prior["valid_from"] - observed_at).total_seconds()) < 1
            if same_instant and abs(prior["value_num"] - value) > settings.value_tolerance:
                # leave both active; tie-breaker decides
                c.execute("UPDATE fact_claims SET status='contested' WHERE id IN (%s,%s)", (prior["id"], cid))
                c.execute("INSERT INTO graph_edges(src_id,dst_id,relation) VALUES (%s,%s,'CONTRADICTS')", (cid, prior["id"]))
            elif abs(prior["value_num"] - value) > settings.value_tolerance:
                c.execute("UPDATE fact_claims SET valid_to=%s, status='superseded' WHERE id=%s", (observed_at, prior["id"]))
                c.execute("UPDATE fact_claims SET supersedes=%s WHERE id=%s", (prior["id"], cid))
                c.execute("UPDATE temporal_embeddings SET valid_to=%s WHERE id=(SELECT embedding_id FROM fact_claims WHERE id=%s)",
                          (observed_at, prior["id"]))
                c.execute("INSERT INTO graph_edges(src_id,dst_id,relation) VALUES (%s,%s,'SUPERSEDES')", (cid, prior["id"]))
    return cid


def resolve_contested(entity_id: str, attribute: str) -> dict | None:
    """ABSA-weighted tie-breaker for simultaneous contradictory ground truths.

    confidence = 0.55 * legal/numeric syntax + 0.30 * FinBERT neutral prob + 0.15 * decimal precision
    Marketing prose (positive sentiment, exclamations) loses to explicit legal syntax."""
    rows = db.fetchall(
        """SELECT id, value_num, evidence, valid_from FROM fact_claims
           WHERE entity_id=%s AND attribute=%s AND status='contested' ORDER BY valid_from DESC""",
        (entity_id, attribute))
    if len(rows) < 2:
        return None
    scored = []
    for r in rows:
        ev = r["evidence"] or ""
        s = nlp.sentiment(ev)
        precision = 1.0 if "." in f"{r['value_num']}" and len(f"{r['value_num']}".split(".")[1]) >= 2 else 0.4
        conf = 0.55 * nlp.legal_syntax_score(ev) + 0.30 * s["neutral"] + 0.15 * precision
        scored.append({"id": str(r["id"]), "value": r["value_num"], "evidence": ev, "sentiment": s,
                       "legal_syntax": nlp.legal_syntax_score(ev), "confidence": round(conf, 4)})
    scored.sort(key=lambda x: -x["confidence"])
    winner, losers = scored[0], scored[1:]
    with db.conn() as c:
        c.execute("UPDATE fact_claims SET status='active', is_ground_truth=true, confidence=%s WHERE id=%s",
                  (winner["confidence"], winner["id"]))
        for lo in losers:
            c.execute("""UPDATE fact_claims SET status='superseded', is_ground_truth=false, confidence=%s,
                         valid_to=valid_from WHERE id=%s""", (lo["confidence"], lo["id"]))
    logbus.emit("graph", f"tie-breaker resolved {attribute}: {winner['value']} beats "
                f"{', '.join(str(lo['value']) for lo in losers)}", winner=winner["value"])
    return {"winner": winner, "losers": losers}


# ------------------------------------------------------------------ reads / maths

def decay(age_days: float, half_life: float | None) -> float:
    if half_life is None:
        return 1.0
    return 0.5 ** (max(age_days, 0.0) / half_life)


def naive_weight(link_count: int) -> float:
    """How an LLM's statistical prior weights a claim: volume x link popularity."""
    return 1.0 + math.log1p(max(link_count, 0))


@dataclass
class Cluster:
    value: float
    naive_mass: float = 0.0
    temporal_mass: float = 0.0
    n: int = 0
    sources: dict = None

    def as_dict(self, total_naive: float, total_temporal: float) -> dict:
        return {"value": self.value, "claims": self.n,
                "naive_mass": round(self.naive_mass, 4), "temporal_mass": round(self.temporal_mass, 6),
                "naive_share": round(self.naive_mass / total_naive, 6) if total_naive else 0,
                "temporal_share": round(self.temporal_mass / total_temporal, 6) if total_temporal else 0,
                "sources": self.sources}


def current_ground_truth(entity_id: str, attribute: str) -> dict | None:
    return db.fetchone(
        """SELECT * FROM fact_claims WHERE entity_id=%s AND attribute=%s AND is_ground_truth
           AND status='active' AND valid_to IS NULL ORDER BY valid_from DESC, confidence DESC LIMIT 1""",
        (entity_id, attribute))


def corroboration(entity_id: str, attribute: str, at: datetime | None = None, persist: bool = True) -> dict:
    at = at or now()
    resolve_contested(entity_id, attribute)
    gt = current_ground_truth(entity_id, attribute)
    claims = db.fetchall(
        """SELECT value_num, source_type, observed_at, link_count, authority, is_ground_truth, status
           FROM fact_claims WHERE entity_id=%s AND attribute=%s AND observed_at <= %s""",
        (entity_id, attribute, at))
    if not claims:
        return {"entity_id": entity_id, "attribute": attribute, "claims": 0}
    tol = settings.value_tolerance
    clusters: list[Cluster] = []
    stale = 0
    penalty_mass = 0.0
    for c in claims:
        v = round(c["value_num"], 4)
        cl = next((x for x in clusters if abs(x.value - v) <= tol), None)
        if cl is None:
            cl = Cluster(v, sources={})
            clusters.append(cl)
        nw = naive_weight(c["link_count"])
        age = (at - c["observed_at"]).total_seconds() / 86400
        tw = c["authority"] * decay(age, settings.half_life_days.get(c["source_type"])) * nw
        if c["source_type"] in INSTITUTIONAL_SOURCES and c["status"] != "active":
            tw *= 0.0                                      # superseded official versions carry no weight
        if gt is not None and abs(v - gt["value_num"]) > tol:
            if c["observed_at"] < gt["valid_from"] or c["source_type"] not in INSTITUTIONAL_SOURCES:
                tw *= (1 - settings.supersession_penalty)  # Corroboration Deficit penalty
                stale += 1
                penalty_mass += nw - tw
        cl.naive_mass += nw
        cl.temporal_mass += tw
        cl.n += 1
        cl.sources[c["source_type"]] = cl.sources.get(c["source_type"], 0) + 1
    tn = sum(c.naive_mass for c in clusters)
    tt = sum(c.temporal_mass for c in clusters)
    clusters.sort(key=lambda c: -c.naive_mass)
    naive_answer = clusters[0].value
    graph_answer = max(clusters, key=lambda c: c.temporal_mass).value
    gt_cluster = next((c for c in clusters if gt and abs(c.value - gt["value_num"]) <= tol), None)
    naive_share = gt_cluster.naive_mass / tn if gt_cluster and tn else 0.0
    temporal_share = gt_cluster.temporal_mass / tt if gt_cluster and tt else 0.0
    # sentiment of retail forum text about this entity (ABSA rollup)
    sent = db.fetchone(
        """SELECT avg((sentiment->>'positive')::float - (sentiment->>'negative')::float) AS pol
           FROM temporal_embeddings WHERE entity_id=%s AND source_type='retail_forum' AND sentiment IS NOT NULL""",
        (entity_id,))
    result = {
        "entity_id": entity_id, "attribute": attribute, "computed_at": at.isoformat(),
        "claims": len(claims), "stale_claims": stale,
        "ground_truth": None if not gt else {
            "id": str(gt["id"]), "value": gt["value_num"], "unit": gt["unit"], "source_type": gt["source_type"],
            "source_url": gt["source_url"], "valid_from": gt["valid_from"].isoformat(), "evidence": gt["evidence"]},
        "naive_llm_answer": naive_answer,
        "graphrag_answer": graph_answer,
        "hallucination_prevented": bool(gt and abs(naive_answer - gt["value_num"]) > tol
                                        and abs(graph_answer - gt["value_num"]) <= tol),
        "naive_gt_share": round(naive_share, 6),
        "temporal_gt_share": round(temporal_share, 6),
        "corroboration_deficit": round(1 - naive_share, 6),
        "deficit_recovered": round(temporal_share - naive_share, 6),
        "penalty_mass": round(penalty_mass, 3),
        "retail_sentiment": round(sent["pol"], 4) if sent and sent["pol"] is not None else None,
        "clusters": [c.as_dict(tn, tt) for c in clusters],
    }
    if persist:
        db.execute(
            """INSERT INTO corroboration_logs(entity_id,attribute,ground_truth_value,ground_truth_claim,naive_gt_share,
                   temporal_gt_share,corroboration_deficit,stale_claims,retail_sentiment,details)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (entity_id, attribute, gt["value_num"] if gt else None, gt["id"] if gt else None, naive_share,
             temporal_share, 1 - naive_share, stale, result["retail_sentiment"],
             db.jsonb({"clusters": result["clusters"], "naive_answer": naive_answer, "graph_answer": graph_answer})))
    return result


def timeline(entity_id: str, attribute: str, buckets: int = 24) -> dict:
    """Temporal mutation of the narrative: per time bucket, claim mass per value (for the chart)."""
    rows = db.fetchall(
        """SELECT value_num, source_type, observed_at, link_count FROM fact_claims
           WHERE entity_id=%s AND attribute=%s ORDER BY observed_at""", (entity_id, attribute))
    if not rows:
        return {"points": [], "series": []}
    t0, t1 = rows[0]["observed_at"], max(now(), rows[-1]["observed_at"])
    span = max((t1 - t0).total_seconds(), 1)
    values = sorted({round(r["value_num"], 2) for r in rows})
    pts = [{"t": (t0.timestamp() + span * i / buckets) * 1000} | {str(v): 0.0 for v in values}
           for i in range(buckets + 1)]
    official = []
    for r in rows:
        i = min(int((r["observed_at"] - t0).total_seconds() / span * buckets), buckets)
        pts[i][str(round(r["value_num"], 2))] += naive_weight(r["link_count"])
        if r["source_type"] in INSTITUTIONAL_SOURCES:
            official.append({"t": r["observed_at"].timestamp() * 1000, "value": r["value_num"],
                             "source": r["source_type"]})
    return {"series": [str(v) for v in values], "points": pts, "official": official}


def graph_view(entity_id: str, attribute: str) -> dict:
    """Nodes/edges for the graph panel (value clusters + official versions)."""
    corr = corroboration(entity_id, attribute, persist=False)
    versions = db.fetchall(
        """SELECT id, value_num, valid_from, valid_to, status, source_type, source_url, supersedes, confidence
           FROM fact_claims WHERE entity_id=%s AND attribute=%s AND source_type IN ('institutional_filing','institutional_web')
           ORDER BY valid_from""", (entity_id, attribute))
    return {"corroboration": corr, "timeline": timeline(entity_id, attribute),
            "versions": [{**v, "id": str(v["id"]), "supersedes": str(v["supersedes"]) if v["supersedes"] else None}
                         for v in versions]}


def entity_attributes(entity_id: str) -> list[str]:
    return [r["attribute"] for r in db.fetchall(
        "SELECT DISTINCT attribute FROM fact_claims WHERE entity_id=%s ORDER BY attribute", (entity_id,))]


def resolve_entity(institution_id: str, hint: str | None, default_id: str | None) -> str | None:
    """Map a product mention to an entity node by alias/token overlap."""
    if not hint:
        return default_id
    ents = db.fetchall("SELECT id, entity_name, aliases FROM entity_nodes WHERE institution_id=%s", (institution_id,))
    ht = set(nlp.tokens(hint))
    best, score = default_id, 0.0
    for e in ents:
        for name in [e["entity_name"], *e["aliases"]]:
            nt = set(nlp.tokens(name))
            if not nt:
                continue
            j = len(ht & nt) / len(ht | nt)
            if j > score:
                best, score = str(e["id"]), j
    return best if score >= 0.34 else default_id
