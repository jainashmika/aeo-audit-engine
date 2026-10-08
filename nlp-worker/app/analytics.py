"""Context Severance (Req 3.x) and Sub-Entity Partitioning / Semantic Dilution (Req 4.x)."""
from __future__ import annotations

import numpy as np

from . import db, graph, logbus, nlp
from .config import settings

# ------------------------------------------------------------------ context severance


def _page_vec(p: dict) -> np.ndarray:
    """Hybrid dense + sparse vector. The dense half is the stored transformer embedding, the sparse
    half is the deterministic lexical hash. Cosine on the concatenation equals the mean of both
    cosines, the standard hybrid-retrieval score, which keeps the 0.75 threshold meaningful whichever
    dense model is loaded (in lite mode both halves are the same encoder)."""
    dense = np.asarray(p["embedding"], dtype=np.float32) if p.get("embedding") is not None \
        else nlp.embed(p["rendered_text"] or "")
    return _hybrid(dense, nlp.lite_embed(p["rendered_text"] or ""))


def _hybrid(dense: np.ndarray, sparse: np.ndarray) -> np.ndarray:
    return np.concatenate([dense, sparse]) / np.sqrt(2)


def severance(slug: str, query: str, landing_url: str | None = None, persist: bool = True) -> dict:
    inst = db.fetchone("SELECT * FROM institutions WHERE slug=%s", (slug,))
    pages = db.fetchall("SELECT id,url,title,namespace_type,is_landing,rendered_text,embedding FROM pages "
                        "WHERE institution_id=%s", (inst["id"],))
    if not pages:
        raise ValueError("no pages ingested for institution")
    landing = next((p for p in pages if p["url"] == landing_url), None) or \
        next((p for p in pages if p["is_landing"]), pages[0])
    q = _hybrid(nlp.embed(query), nlp.lite_embed(query))
    ranked = sorted(({"url": p["url"], "title": p["title"], "namespace": p["namespace_type"],
                      "distance": round(1 - nlp.cosine(q, _page_vec(p)), 4)} for p in pages),
                    key=lambda r: r["distance"])
    d_landing = round(1 - nlp.cosine(q, _page_vec(landing)), 4)
    best = ranked[0]
    hydrate = d_landing > settings.severance_threshold
    payload = hydration_payload(slug, query, best["url"]) if hydrate else None
    result = {
        "institution": slug, "query": query, "landing_url": landing["url"], "landing_title": landing["title"],
        "cosine_distance": d_landing, "context_severance_score": d_landing,
        "threshold": settings.severance_threshold, "hydrate": hydrate,
        "best_match": best, "intent_gap": round(d_landing - best["distance"], 4),
        "ranking": ranked[:8], "intents": nlp.intents(query), "hydration": payload,
        "embedding_backend": nlp.status()["embedding"],
    }
    if persist:
        db.execute(
            """INSERT INTO severance_runs(institution_id,query,landing_url,cosine_distance,severance_score,best_match_url,hydrate,payload)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (inst["id"], query, landing["url"], d_landing, d_landing, best["url"], hydrate, db.jsonb(payload)))
        logbus.emit("severance", f"CSS={d_landing:.3f} for \"{query[:60]}\" -> "
                    + ("HYDRATE " + best["url"] if hydrate else "within tolerance"),
                    "WARN" if hydrate else "INFO")
    return result


def hydration_payload(slug: str, query: str, target_url: str) -> dict:
    """Contextual UI Hydration: text payload + an injectable script."""
    from . import payloads  # local import to avoid a cycle
    page = db.fetchone("SELECT p.*, i.name AS inst_name FROM pages p JOIN institutions i ON i.id=p.institution_id "
                       "WHERE p.url=%s", (target_url,))
    facts = payloads.current_facts(slug)
    qtok = set(nlp.tokens(query))
    rel = []
    title_tok = set(nlp.tokens(page["title"] or "")) if page else set()
    for f in facts:
        etok = set(nlp.tokens(f["entity"]))
        score = len(qtok & (etok | set(nlp.tokens(f["attribute"].replace("_", " ")))))
        if etok and etok <= title_tok:
            score += 3          # facts about the product the best-matching page is about come first
        if score:
            rel.append((score, f))
    rel.sort(key=lambda x: (-x[0], x[1]["entity"], x[1]["attribute"]))
    picked = [f for _, f in rel[:6]]
    headline = page["title"] if page else "Relevant products"
    lines = [f"- **{f['entity']}**: {f['attribute'].replace('_', ' ')} {f['value']}{f['unit'] if f['unit'] == '%' else ' ' + f['unit']}"
             f" (as of {f['valid_from'][:10]})" for f in picked]
    text = f"### You asked: \"{query}\"\n\n{headline}\n\n" + "\n".join(lines) + f"\n\n[Open the full details]({target_url})"
    script = payloads.hydration_script(query, headline, target_url, picked)
    return {"target_url": target_url, "headline": headline, "facts": picked, "markdown": text, "script": script}


# ------------------------------------------------------------------ sub-entity partitioning

PROTOTYPES = {
    "Retail": "retail banking savings account credit card branch everyday customers mass market SIP small "
              "investors regular plan distributor commission customer care helpline personal loan",
    "Institutional": "institutional high net worth hnw corporate treasury family office mandate quantitative "
                     "strategies direct institutional share class relationship manager minimum ₹ crore "
                     "portfolio management services alternative investment",
}


def partition(slug: str, persist: bool = True) -> dict:
    """Assign every text node of the brand to a namespace, measure dilution and attribute bleed."""
    inst = db.fetchone("SELECT * FROM institutions WHERE slug=%s", (slug,))
    iid = inst["id"]
    docs = db.fetchall(
        """SELECT te.id, te.content, te.source_type, te.namespace_type, te.embedding, te.link_count,
                  en.namespace_type AS entity_ns, en.entity_name
           FROM temporal_embeddings te LEFT JOIN entity_nodes en ON en.id=te.entity_id
           WHERE en.institution_id=%s""", (iid,))
    pages = db.fetchall("SELECT id, rendered_text AS content, namespace_type, embedding FROM pages WHERE institution_id=%s",
                        (iid,))
    proto = {k: nlp.embed(v) for k, v in PROTOTYPES.items()}
    # unique vectors only (10k forum posts collapse onto few templates)
    groups: dict[str, dict] = {}
    for d in docs:
        key = d["content"][:500]
        g = groups.setdefault(key, {"content": d["content"], "vec": np.asarray(d["embedding"], dtype=np.float32),
                                    "weight": 0.0, "label": d["namespace_type"] or d["entity_ns"],
                                    "source": d["source_type"], "entity": d["entity_name"]})
        g["weight"] += graph.naive_weight(d["link_count"])
    for p in pages:
        if p["embedding"] is None:
            continue
        groups.setdefault("page:" + str(p["id"]), {"content": p["content"] or "", "vec": np.asarray(p["embedding"], dtype=np.float32),
                                                    "weight": 1.0, "label": p["namespace_type"], "source": "page",
                                                    "entity": None})
    items = list(groups.values())
    if not items:
        return {"institution": slug, "items": 0}
    # seeded 2-means: start at prototypes (refined by labelled nodes), iterate
    cents = {k: v.copy() for k, v in proto.items()}
    for _ in range(6):
        buckets = {k: [] for k in cents}
        for it in items:
            sims = {k: nlp.cosine(it["vec"], c) for k, c in cents.items()}
            if it["label"] in cents and it["source"] != "retail_forum":
                lab = it["label"]           # official namespace tags are anchors
            else:
                lab = max(sims, key=sims.get)
            it["assigned"], it["sims"] = lab, sims
            buckets[lab].append(it)
        for k, b in buckets.items():
            if b:
                m = np.mean([x["vec"] for x in b], axis=0)
                cents[k] = m / (np.linalg.norm(m) or 1)
    total_w = sum(it["weight"] for it in items)
    brand = np.sum([it["vec"] * it["weight"] for it in items], axis=0)
    brand = brand / (np.linalg.norm(brand) or 1)
    s_r, s_i = nlp.cosine(brand, cents["Retail"]), nlp.cosine(brand, cents["Institutional"])
    dilution = s_r / (s_r + s_i) if (s_r + s_i) else 0.5
    mass = {k: round(sum(it["weight"] for it in items if it["assigned"] == k) / total_w, 4) for k in cents}

    bleed = attribute_bleed(str(iid))
    result = {
        "institution": slug, "nodes": len(items), "weighted_nodes": round(total_w, 2),
        "semantic_dilution_index": round(dilution, 4),
        "brand_similarity": {"Retail": round(s_r, 4), "Institutional": round(s_i, 4)},
        "namespace_mass": mass,
        "centroid_separation": round(1 - nlp.cosine(cents["Retail"], cents["Institutional"]), 4),
        "attribute_bleed": bleed,
        "scatter": _scatter(items),
    }
    if persist:
        db.execute("INSERT INTO dilution_runs(institution_id,dilution_index,attribute_bleed,details) VALUES (%s,%s,%s,%s)",
                   (iid, dilution, bleed["rate"], db.jsonb({k: v for k, v in result.items() if k != "scatter"})))
        logbus.emit("partition", f"{slug}: dilution {dilution:.2f}, attribute bleed {bleed['rate']:.0%} "
                    f"across {len(items)} unique text nodes", "WARN" if bleed["rate"] > 0.2 else "INFO")
    return result


def _scatter(items: list[dict]) -> list[dict]:
    """2-D projection for the dashboard: (sim to Retail, sim to Institutional)."""
    out = []
    for it in sorted(items, key=lambda x: -x["weight"])[:160]:
        out.append({"x": round(it["sims"]["Retail"], 4), "y": round(it["sims"]["Institutional"], 4),
                    "namespace": it["assigned"], "weight": round(it["weight"], 2), "source": it["source"],
                    "label": (it["entity"] or "page") + ": " + it["content"][:90]})
    return out


def attribute_bleed(institution_id: str) -> dict:
    """Share of third-party claims about Institutional entities that carry a Retail namespace value
    (e.g. forum posts quoting the retail 1.25% fee for the institutional fund)."""
    rows = db.fetchall(
        """SELECT en.entity_name, fc.attribute, fc.value_num, fc.source_type
           FROM fact_claims fc JOIN entity_nodes en ON en.id=fc.entity_id
           WHERE en.institution_id=%s AND en.namespace_type='Institutional'
             AND fc.source_type NOT IN ('institutional_filing','institutional_web')""", (institution_id,))
    retail_vals = db.fetchall(
        """SELECT DISTINCT fc.attribute, round(fc.value_num::numeric, 2) AS v FROM fact_claims fc
           JOIN entity_nodes en ON en.id=fc.entity_id
           WHERE en.institution_id=%s AND en.namespace_type='Retail' AND fc.is_ground_truth""", (institution_id,))
    rset = {(r["attribute"], float(r["v"])) for r in retail_vals}
    bled = [r for r in rows if (r["attribute"], round(r["value_num"], 2)) in rset]
    examples = {}
    for r in bled:
        k = f"{r['entity_name']} / {r['attribute']} = {r['value_num']}"
        examples[k] = examples.get(k, 0) + 1
    return {"third_party_claims": len(rows), "bled_claims": len(bled),
            "rate": round(len(bled) / len(rows), 4) if rows else 0.0,
            "examples": [{"claim": k, "count": v} for k, v in sorted(examples.items(), key=lambda x: -x[1])[:5]]}


def namespaced_answer(slug: str, entity_slug: str, attribute: str) -> dict:
    """Retrieval comparison for one institutional question: brand-level vs partitioned."""
    inst = db.fetchone("SELECT id FROM institutions WHERE slug=%s", (slug,))
    ent = db.fetchone("SELECT * FROM entity_nodes WHERE institution_id=%s AND slug=%s", (inst["id"], entity_slug))
    q = nlp.embed(f"{ent['entity_name']} {attribute.replace('_', ' ')}")
    # brand-level retrieval: top-k nearest text nodes of the whole brand, majority value wins
    rows = db.fetchall(
        """SELECT fc.value_num, fc.link_count FROM temporal_embeddings te
           JOIN fact_claims fc ON fc.embedding_id = te.id
           JOIN entity_nodes en ON en.id = fc.entity_id
           WHERE en.institution_id=%s AND fc.attribute=%s
           ORDER BY te.embedding <=> %s LIMIT 200""", (inst["id"], attribute, db.vec(q)))
    votes: dict[float, float] = {}
    for r in rows:
        votes[round(r["value_num"], 2)] = votes.get(round(r["value_num"], 2), 0) + graph.naive_weight(r["link_count"])
    brand_answer = max(votes, key=votes.get) if votes else None
    gt = graph.current_ground_truth(str(ent["id"]), attribute)
    return {"entity": ent["entity_name"], "attribute": attribute, "brand_level_answer": brand_answer,
            "brand_votes": {str(k): round(v, 2) for k, v in sorted(votes.items())},
            "partitioned_answer": gt["value_num"] if gt else None,
            "hallucination_prevented": bool(gt and brand_answer is not None and abs(brand_answer - gt["value_num"]) > 0.05)}
