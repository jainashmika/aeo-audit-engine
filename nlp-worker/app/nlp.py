"""Financial NLP pipeline.

* Embeddings: sentence-transformers (768-d, all-mpnet-base-v2 by default) or a
  deterministic 768-d feature-hashing encoder when models are unavailable.
* Sentiment / ABSA: FinBERT (ProsusAI/finbert) or a Loughran-McDonald style lexicon.
* Entity extraction: rule-based financial NER for rates, yields, fees, tickers and
  product names (FinBERT is a classifier, not a tagger, so numbers come from rules
  and FinBERT scores the sentence each number sits in).
* Intent mining: embedding similarity against intent prototypes.
"""
from __future__ import annotations

import hashlib
import math
import re
import threading
from dataclasses import dataclass, field

import numpy as np

from .config import settings

DIM = settings.embedding_dim
_lock = threading.Lock()

# ---------------------------------------------------------------- backends


class _State:
    mode = "uninitialised"           # "transformers" or "lite"
    embedder = None
    sentiment = None
    detail: dict = {}


STATE = _State()


def load_models() -> dict:
    """Try to load real models; fall back to deterministic lite encoders."""
    with _lock:
        if STATE.mode != "uninitialised":
            return status()
        STATE.detail = {}
        if settings.nlp_mode != "lite":
            try:
                from sentence_transformers import SentenceTransformer
                emb = SentenceTransformer(settings.embedding_model, device="cpu")
                if emb.get_sentence_embedding_dimension() != DIM:
                    raise ValueError(f"embedding model must be {DIM}-d")
                STATE.embedder = emb
                STATE.detail["embedding"] = settings.embedding_model
            except Exception as e:  # noqa: BLE001
                STATE.detail["embedding_error"] = repr(e)[:300]
            try:
                from transformers import pipeline
                STATE.sentiment = pipeline("text-classification", model=settings.sentiment_model,
                                           top_k=None, truncation=True, device=-1)
                STATE.detail["sentiment"] = settings.sentiment_model
            except Exception as e:  # noqa: BLE001
                STATE.detail["sentiment_error"] = repr(e)[:300]
        STATE.mode = "transformers" if (STATE.embedder or STATE.sentiment) else "lite"
        STATE.detail.setdefault("embedding", "feature-hashing-768 (lite)")
        STATE.detail.setdefault("sentiment", "finance-lexicon (lite)")
        return status()


def status() -> dict:
    return {"mode": STATE.mode, "embedding": "feature-hashing-768 (lite)",
            "sentiment": "finance-lexicon (lite)", **STATE.detail}


# ---------------------------------------------------------------- tokenising

_TOKEN = re.compile(r"[a-z]+(?:'[a-z]+)?|\d+(?:\.\d+)?%?|[<>≤≥]")
_STOP = set("""a an the of and or to in on for with is are was were be been it its this that
these those as at by from our your we you they their i me my us not no but if then so than
very can will just about into over under more most less such also""".split())
_CANON = {
    "funds": "fund", "etfs": "etf", "ratios": "ratio", "accounts": "account", "loans": "loan",
    "yields": "yield", "rates": "rate", "fees": "fee", "charges": "fee", "ter": "expense_ratio",
    "mortgage": "home_loan", "housing": "home_loan", "esg": "esg", "sustainable": "esg",
    "responsible": "esg", "green": "esg", "pension": "retirement", "nps": "retirement",
    "superannuation": "retirement", "hni": "hnw", "wealthy": "hnw", "affluent": "hnw",
    "institutional": "institution", "institutions": "institution", "corporate": "institution",
    "treasury": "institution", "dividend": "yield", "apr": "rate", "interest": "rate",
}


def tokens(text: str) -> list[str]:
    out = []
    for t in _TOKEN.findall(text.lower()):
        if t in _STOP:
            continue
        if t.endswith("%"):
            out += ["<pct>", "pct_" + t[:-1]]
            continue
        if re.fullmatch(r"\d+(\.\d+)?", t):
            out.append("<num>")
            continue
        out.append(_CANON.get(t, t))
    # bigram canonicalisation for multi-word finance terms
    joined = " ".join(out)
    joined = joined.replace("expense ratio", "expense_ratio").replace("tax advantaged", "tax_advantaged") \
        .replace("high net worth", "hnw").replace("home_loan loan", "home_loan").replace("home loan", "home_loan")
    return joined.split()


def _bucket(feature: str) -> tuple[int, float]:
    h = hashlib.blake2b(feature.encode(), digest_size=8).digest()
    idx = int.from_bytes(h[:4], "little") % DIM
    sign = 1.0 if h[4] & 1 else -1.0
    return idx, sign


def lite_embed(text: str) -> np.ndarray:
    """Deterministic 768-d hashed bag of unigrams + bigrams with sublinear tf."""
    toks = tokens(text)
    counts: dict[str, int] = {}
    for i, t in enumerate(toks):
        counts[t] = counts.get(t, 0) + 1
        if i + 1 < len(toks):
            bg = t + "__" + toks[i + 1]
            counts[bg] = counts.get(bg, 0) + 1
    v = np.zeros(DIM, dtype=np.float32)
    for f, c in counts.items():
        idx, sign = _bucket(f)
        w = (1 + math.log(c)) * (0.6 if "__" in f else 1.0) * (0.4 if f in ("<num>", "<pct>") else 1.0)
        v[idx] += sign * w
    n = np.linalg.norm(v)
    return v / n if n else v


def chunk(text: str, max_words: int = 160) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    return [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]


_CACHE: dict[str, bytes] = {}


def _compute(text: str) -> np.ndarray:
    if STATE.embedder is not None:
        parts = chunk(text)
        mat = STATE.embedder.encode(parts, normalize_embeddings=True, show_progress_bar=False)
        v = np.asarray(mat, dtype=np.float32).mean(axis=0)
        return (v / (np.linalg.norm(v) or 1.0)).astype(np.float32)
    return lite_embed(text)


def embed(text: str) -> np.ndarray:
    t = text.strip()[:20000]
    b = _CACHE.get(t)
    if b is None:
        b = _compute(t).tobytes()
        if len(_CACHE) < 60000:
            _CACHE[t] = b
    return np.frombuffer(b, dtype=np.float32).copy()


def embed_many(texts: list[str]) -> list[np.ndarray]:
    """Batch-encode unique short texts once (10k forum posts share ~40 templates)."""
    if STATE.embedder is not None:
        missing = [t for t in dict.fromkeys(x.strip()[:20000] for x in texts)
                   if t not in _CACHE and len(t.split()) <= 160]
        for i in range(0, len(missing), 128):
            part = missing[i:i + 128]
            mat = STATE.embedder.encode(part, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
            for t, row in zip(part, mat):
                _CACHE[t] = np.asarray(row, dtype=np.float32).tobytes()
    return [embed(t) for t in texts]


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if not na or not nb:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def content_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode()).hexdigest()


# ---------------------------------------------------------------- sentiment / ABSA

_POS = set("""strong gain gains growth outperform outperformed beat beats best higher record improve improved
improvement exceptional attractive superior premium robust upside lucrative rewarding unmatched leading
award winning love great amazing excellent""".split())
_NEG = set("""loss losses decline declined weak worse worst lower underperform risk risky fee fees penalty
penalties expensive scam avoid terrible poor hidden charges complaint complaints bad slow costly""".split())
_LEGAL = re.compile(
    r"\b(w\.?e\.?f\.?|with effect from|pursuant|scheme information document|sid|kim|sebi|sec\b|regulation|"
    r"disclaimer|subject to market risks|statutory|as on|as of|per annum|p\.a\.|annuali[sz]ed|"
    r"offer document|prospectus|notified|circular|clause|hereby)\b", re.I)


def sentiment(text: str) -> dict:
    """Return {'positive','negative','neutral'} probabilities."""
    if STATE.sentiment is not None:
        try:
            res = STATE.sentiment(text[:2000])
            rows = res[0] if isinstance(res[0], list) else res
            d = {r["label"].lower(): float(r["score"]) for r in rows}
            return {k: round(d.get(k, 0.0), 4) for k in ("positive", "negative", "neutral")}
        except Exception:  # noqa: BLE001
            pass
    toks = re.findall(r"[a-z]+", text.lower())
    p = sum(t in _POS for t in toks)
    n = sum(t in _NEG for t in toks)
    excl = text.count("!")
    p += excl
    neutral = 1.0 + 0.15 * len(_LEGAL.findall(text)) + 0.02 * len(toks)
    z = p + n + neutral
    return {"positive": round(p / z, 4), "negative": round(n / z, 4), "neutral": round(neutral / z, 4)}


def legal_syntax_score(text: str) -> float:
    """0..1 how much a passage reads as explicit numerical / legal syntax rather than marketing prose."""
    legal = len(_LEGAL.findall(text))
    precise = len(re.findall(r"\d+\.\d{2}\s?%", text))
    exclaim = text.count("!")
    superl = len(re.findall(r"\b(best|unmatched|incredible|amazing|now offering|introducing|new)\b", text, re.I))
    raw = 0.35 * legal + 0.25 * precise - 0.3 * exclaim - 0.15 * superl
    return round(1 / (1 + math.exp(-raw)), 4)


def absa(text: str, aspects: list[str]) -> list[dict]:
    """Aspect-Based Sentiment: score the sentences that mention each aspect."""
    sents = re.split(r"(?<=[.!?])\s+", text)
    out = []
    for a in aspects:
        hits = [s for s in sents if a.lower().replace("_", " ") in s.lower()]
        if not hits:
            continue
        scores = [sentiment(s) for s in hits]
        avg = {k: round(sum(s[k] for s in scores) / len(scores), 4) for k in ("positive", "negative", "neutral")}
        out.append({"aspect": a, "mentions": len(hits), "sentiment": avg,
                    "polarity": round(avg["positive"] - avg["negative"], 4)})
    return out


# ---------------------------------------------------------------- financial entity extraction

ATTR_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("expense_ratio", re.compile(r"(?:total\s+)?expense\s+ratio|\bTER\b", re.I)),
    ("yield", re.compile(r"(?:dividend|distribution|annual|current)?\s*yield", re.I)),
    ("apr", re.compile(r"\bAPR\b|annual\s+percentage\s+rate", re.I)),
    ("interest_rate", re.compile(r"interest\s+rate|home\s+loan\s+rate|mortgage\s+rate|lending\s+rate|rate\s+of\s+interest|\brate\b", re.I)),
    ("exit_load", re.compile(r"exit\s+load", re.I)),
    ("processing_fee", re.compile(r"processing\s+fee", re.I)),
]
COMPARATOR = re.compile(r"(below|under|less than|lower than|above|over|more than|higher than|<|>|≤|≥)\s*$", re.I)
PCT = re.compile(r"(\d{1,3}(?:\.\d{1,3})?)\s?(?:%|per\s?cent|percent)", re.I)
INR = re.compile(r"(?:₹|\brs\.?|\binr)\s?(\d[\d,]*(?:\.\d+)?)\s*(crore|lakh|cr\b|l\b)?", re.I)
TICKER = re.compile(r"\b(?:NSE|BSE|NYSE|NASDAQ)\s?:\s?([A-Z][A-Z0-9&]{1,14})\b")
PRODUCT = re.compile(r"\b((?:[A-Z][A-Za-z0-9&\-]+\s){0,6}(?:Fund|ETF|Loan|Account|Bond|Card|Portfolio|Strategy|Plan))\b")


_LEAD = {"the", "a", "an", "our", "your", "introducing", "new", "disclaimer", "following", "why", "is", "psa",
         "compared", "my", "holding", "switched", "anyone", "just", "wow", "heard", "own", "get", "open", "visit", "with"}


def clean_product(name: str | None) -> str | None:
    if not name:
        return None
    words = name.split()
    while len(words) > 1 and words[0].lower().strip(":,") in _LEAD:
        words = words[1:]
    return " ".join(words)


@dataclass
class Fact:
    attribute: str
    value: float
    unit: str
    sentence: str
    product_hint: str | None = None
    confidence: float = 0.5
    meta: dict = field(default_factory=dict)

    def key(self) -> tuple:
        return (self.attribute, round(self.value, 2))


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def extract_facts(text: str) -> list[Fact]:
    facts: list[Fact] = []
    seen = set()
    for s in _sentences(text):
        pcts = list(PCT.finditer(s))
        if pcts:
            prev_end = 0
            for m in pcts:
                lo = max(prev_end, m.start() - 70)
                prev_end = m.end()
                window = s[lo: m.start()]
                if COMPARATOR.search(window[-16:]):
                    continue  # "well below 0.5%" is a comparison, not a fact
                after = s[m.end(): m.end() + 30]
                attr = None
                best_pos = -1
                for name, pat in ATTR_PATTERNS:
                    for am in pat.finditer(window):
                        if am.start() > best_pos:
                            best_pos, attr = am.start(), name
                if attr is None:
                    for name, pat in ATTR_PATTERNS:
                        if pat.search(after):
                            attr = name
                            break
                if attr is None:
                    continue
                val = float(m.group(1))
                prod = PRODUCT.search(s)
                f = Fact(attr, val, "%", s[:400], clean_product(prod.group(1).strip()) if prod else None,
                         confidence=0.55 + 0.4 * legal_syntax_score(s))
                if (f.key(), f.product_hint) not in seen:
                    seen.add((f.key(), f.product_hint))
                    facts.append(f)
        for m in INR.finditer(s):
            if re.search(r"minimum|min\.|invest", s, re.I):
                amt = float(m.group(1).replace(",", ""))
                mult = {"crore": 1e7, "cr": 1e7, "lakh": 1e5, "l": 1e5}.get((m.group(2) or "").lower(), 1)
                f = Fact("min_investment", amt * mult, "INR", s[:400])
                if (f.key(), None) not in seen:
                    seen.add((f.key(), None))
                    facts.append(f)
    return facts


_JSON_KEY_ATTR = [
    (re.compile(r"expense|ter\b", re.I), "expense_ratio", "%"),
    (re.compile(r"yield|dividend", re.I), "yield", "%"),
    (re.compile(r"\bapr\b", re.I), "apr", "%"),
    (re.compile(r"rate|roi|interest", re.I), "interest_rate", "%"),
    (re.compile(r"min.*invest", re.I), "min_investment", "INR"),
]


def facts_from_json(obj, path: str = "", product: str | None = None) -> list[Fact]:
    """Structured extraction from intercepted XHR JSON (calculator APIs)."""
    out: list[Fact] = []
    if isinstance(obj, dict):
        prod = obj.get("product") or obj.get("productName") or obj.get("name") or product
        for k, v in obj.items():
            out += facts_from_json(v, f"{path}.{k}" if path else k, prod if isinstance(prod, str) else product)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += facts_from_json(v, f"{path}[{i}]", product)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        leaf = path.split(".")[-1]
        for pat, attr, unit in _JSON_KEY_ATTR:
            if pat.search(leaf):
                val = float(obj)
                if unit == "%" and val < 1 and "bps" not in leaf:   # fractions like 0.0865
                    val = round(val * 100, 4) if val < 0.3 else val
                out.append(Fact(attr, val, unit, f"{path} = {obj}", product, confidence=0.95,
                                meta={"json_path": path}))
                break
    return out


def json_to_text(obj, path: str = "") -> list[str]:
    lines: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            lines += json_to_text(v, f"{path} {k}".strip())
    elif isinstance(obj, list):
        for v in obj:
            lines += json_to_text(v, path)
    elif isinstance(obj, (int, float, str)) and not (isinstance(obj, str) and len(obj) > 200):
        lines.append(f"{path.replace('_', ' ')}: {obj}")
    return lines


def tickers(text: str) -> list[str]:
    return sorted(set(TICKER.findall(text)))


def products(text: str) -> list[str]:
    return sorted({clean_product(m.group(1).strip()) for m in PRODUCT.finditer(text)})


# ---------------------------------------------------------------- intent mining

INTENTS = {
    "yield_seeking": "high dividend yield income fund returns payout distribution",
    "fee_sensitive": "low expense ratio cheap fees cost charges TER",
    "esg_screening": "ESG sustainable responsible green funds climate governance",
    "retirement_tax": "tax advantaged retirement pension NPS 80C ELSS long term",
    "borrowing": "home loan mortgage interest rate EMI borrowing APR",
    "institutional_mandate": "institutional mandate high net worth corporate treasury family office quantitative",
}


def intents(text: str, top: int = 3) -> list[dict]:
    q = embed(text)
    scored = [(name, cosine(q, embed(proto))) for name, proto in INTENTS.items()]
    scored.sort(key=lambda x: -x[1])
    return [{"intent": n, "score": round(s, 4)} for n, s in scored[:top]]


def analyse(text: str) -> dict:
    """One-shot NLP report used by the /nlp/analyse endpoint."""
    facts = extract_facts(text)
    return {
        "backend": status(),
        "sentiment": sentiment(text),
        "legal_syntax_score": legal_syntax_score(text),
        "facts": [f.__dict__ for f in facts],
        "tickers": tickers(text),
        "products": products(text),
        "intents": intents(text),
        "absa": absa(text, sorted({f.attribute for f in facts}) or ["fee", "yield", "rate"]),
    }
