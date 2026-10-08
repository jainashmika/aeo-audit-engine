"""Scraping pipeline (Req 1.1 + edge cases: gated calculators, payload obfuscation,
zero-vector pages).

Two views of every page are produced:
  * static  : what a non-JS AI crawler sees (raw HTML, scripts stripped)
  * rendered: what a human sees after the DOM executes. Produced by Playwright when
              available. Otherwise an XHR interceptor discovers fetch()/XHR endpoints
              referenced by inline scripts, calls them and captures their JSON. That
              emulation is also the strategy for base64 PDF obfuscation: the JSON is
              captured before it is turned into a PDF blob.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from . import nlp
from .config import settings

FILING_HINT = re.compile(r"sebi|sec\b|filing|scheme[-_ ]information|\bsid\b|\bkim\b|factsheet|offer[-_ ]document|"
                         r"prospectus|10-k|n-1a|disclosure", re.I)
FETCH_URL = re.compile(r"""(?:fetch|axios\.get|axios\.post|open)\(\s*(?:['"]GET['"]\s*,\s*)?['"`]([^'"`]+)['"`]""")
_UA = {"User-Agent": "AEO-Audit-Engine/1.0 (+https://github.com/aeo-audit-engine)"}


@dataclass
class PageView:
    url: str
    title: str
    html: str
    static_text: str
    rendered_text: str
    render_mode: str
    intercepted: list[dict] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)
    filings: list[dict] = field(default_factory=list)


def _client() -> httpx.Client:
    return httpx.Client(timeout=20, follow_redirects=True, headers=_UA)


def static_text_of(html: str) -> tuple[str, str, list[dict]]:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""
    links = [{"href": a.get("href"), "text": a.get_text(" ", strip=True)} for a in soup.find_all("a") if a.get("href")]
    for t in soup(["script", "style", "template", "svg"]):
        t.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    return title, text, links


def _inline_json_blobs(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    blobs = []
    for s in soup.find_all("script"):
        if s.get("type") in ("application/json", "application/ld+json") and s.string:
            try:
                blobs.append(json.loads(s.string))
            except json.JSONDecodeError:
                pass
    return blobs


def _intercept(url: str, html: str, client: httpx.Client) -> list[dict]:
    """XHR interception emulation: find endpoints referenced by scripts and capture JSON."""
    soup = BeautifulSoup(html, "html.parser")
    scripts = [s.string or "" for s in soup.find_all("script") if not s.get("src")]
    for s in soup.find_all("script", src=True):
        try:
            scripts.append(client.get(urljoin(url, s["src"])).text)
        except httpx.HTTPError:
            pass
    captured = []
    for src in scripts:
        for ep in dict.fromkeys(FETCH_URL.findall(src)):
            target = urljoin(url, ep)
            try:
                r = client.get(target)
                if "json" in r.headers.get("content-type", "") or r.text.strip()[:1] in "{[":
                    captured.append({"url": target, "status": r.status_code, "json": r.json()})
            except (httpx.HTTPError, json.JSONDecodeError, ValueError):
                continue
    for blob in _inline_json_blobs(html):
        captured.append({"url": url + "#inline-json", "status": 200, "json": blob})
    return captured


def _strip_obfuscation(obj):
    """Drop base64 PDF / binary blobs so only latent values remain."""
    if isinstance(obj, dict):
        return {k: _strip_obfuscation(v) for k, v in obj.items()
                if not (isinstance(v, str) and (v.startswith("JVBERi0") or len(v) > 400))}
    if isinstance(obj, list):
        return [_strip_obfuscation(v) for v in obj]
    return obj


def _render_playwright(url: str) -> tuple[str, list[dict]] | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    captured: list[dict] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page()

            def on_response(resp):
                ct = resp.headers.get("content-type", "")
                if "json" in ct:
                    try:
                        captured.append({"url": resp.url, "status": resp.status, "json": resp.json()})
                    except Exception:  # noqa: BLE001
                        pass
            page.on("response", on_response)
            page.goto(url, wait_until="networkidle", timeout=25000)
            text = page.inner_text("body")
            browser.close()
            return re.sub(r"\s+", " ", text).strip(), captured
    except Exception:  # noqa: BLE001
        return None


def fetch_view(url: str, render: bool = True, html: str | None = None) -> PageView:
    with _client() as client:
        if html is None:
            r = client.get(url)
            r.raise_for_status()
            html = r.text
        title, static, links = static_text_of(html)
        rendered, mode, captured = static, "static-only", []
        if render:
            pw = _render_playwright(url) if settings.render_mode in ("auto", "playwright") else None
            if pw is not None:
                rendered, captured = pw
                mode = "playwright"
            else:
                captured = _intercept(url, html, client)
                mode = "xhr-interceptor"
            captured = [{**c, "json": _strip_obfuscation(c["json"])} for c in captured]
            extra = []
            for c in captured:
                extra += nlp.json_to_text(c["json"])
            if extra:
                rendered = (rendered + " \n" + " \n".join(extra)).strip()
        view = PageView(url, title, html, static, rendered, mode, captured, links)
        # Zero-vector fallback: sparse page -> crawl linked regulatory filings
        if len(nlp.tokens(rendered)) < settings.zero_vector_min_tokens or not _facts_of(view):
            view.filings = _crawl_filings(url, links, client)
    return view


def _crawl_filings(url: str, links: list[dict], client: httpx.Client) -> list[dict]:
    out = []
    base_host = urlparse(url).netloc
    for ln in links:
        href, text = ln["href"], ln["text"]
        if not (FILING_HINT.search(href) or FILING_HINT.search(text)):
            continue
        target = urljoin(url, href)
        host = urlparse(target).netloc
        if host != base_host and not re.search(r"sebi\.gov\.in|sec\.gov|amfiindia", host):
            continue
        try:
            r = client.get(target)
            _, txt, _ = static_text_of(r.text) if "<" in r.text[:200] else ("", r.text, [])
            out.append({"url": target, "text": txt})
        except httpx.HTTPError:
            continue
    return out


def _facts_of(view: PageView) -> list[nlp.Fact]:
    fs = nlp.extract_facts(view.rendered_text)
    for c in view.intercepted:
        fs += nlp.facts_from_json(c["json"])
    return fs


@dataclass
class ExtractionReport:
    static_tokens: int
    rendered_tokens: int
    static_facts: list[nlp.Fact]
    rendered_facts: list[nlp.Fact]
    filing_facts: list[nlp.Fact]
    extraction_loss: float
    token_loss: float
    lost: list[nlp.Fact]


def extraction_loss(view: PageView) -> ExtractionReport:
    """Req 1.1: share of decision-relevant facts invisible to a non-rendering crawler."""
    sf = nlp.extract_facts(view.static_text)
    rf = _dedupe(_facts_of(view) + sf)
    ff: list[nlp.Fact] = []
    for f in view.filings:
        ff += nlp.extract_facts(f["text"])
    ff = _dedupe(ff)
    skeys = {f.key() for f in sf}
    universe = _dedupe(rf + ff)
    lost = [f for f in universe if f.key() not in skeys]
    st, rt = len(nlp.tokens(view.static_text)), len(nlp.tokens(view.rendered_text))
    return ExtractionReport(
        st, rt, sf, rf, ff,
        round(len(lost) / len(universe), 4) if universe else 1.0,
        round(1 - st / rt, 4) if rt else 0.0,
        lost,
    )


def _dedupe(fs: list[nlp.Fact]) -> list[nlp.Fact]:
    seen, out = set(), []
    for f in sorted(fs, key=lambda x: -x.confidence):
        if f.key() not in seen:
            seen.add(f.key())
            out.append(f)
    return out
