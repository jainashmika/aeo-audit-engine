# AEO Audit Engine

Quantifying LLM hallucination and factual drift in financial services via Temporal GraphRAG.

The engine audits what AI answer engines are likely to say about a bank's products, measures four
failure modes from unstructured text, and generates the machine-readable payloads that correct them.
It ships with a seeded demo (two fictional institutions, about 14,500 forum, press and web text nodes)
that reproduces every edge case in the specification, and an executable suite that proves each one.

```
Banking portals ──webhook──▶ Orchestration API ──REST──▶ NLP & Vector Worker ──▶ PostgreSQL + pgvector
                               Spring Boot 21            FastAPI, FinBERT,         temporal graph,
                               scheduler, jobs,          sentence-transformers,    768-d embeddings,
                               GraphQL, REST gateway     Playwright scraper        corroboration logs
                                      ▲
                                      │ /api/* (runtime proxy)
                              Dashboard (Next.js 14, Zustand, Tailwind, Recharts, React-Reflex)
```

## Run it

```bash
docker compose up --build
```

| Service | URL | What it is |
|---|---|---|
| Dashboard | http://localhost:3000 | The Answer-Engine Ledger (Broadsheet and Darcula themes) |
| Orchestration API | http://localhost:8080 | REST gateway, webhooks, schedules, GraphiQL at `/graphiql` |
| NLP worker | http://localhost:8000/docs | FastAPI with OpenAPI docs; demo bank sites at `/demo-sites/` |
| PostgreSQL | localhost:5432 | `aeo` / `aeo`, database `aeo`, pgvector enabled |

First boot downloads FinBERT (`ProsusAI/finbert`) and `all-mpnet-base-v2` into a volume and seeds the
demo; the Wire terminal at the bottom of the dashboard prints `demo ready` when it is done.
For a small, model-free image (deterministic lite encoders, XHR interceptor instead of Chromium):

```bash
INSTALL_ML=false NLP_MODE=lite RENDER_MODE=interceptor docker compose up --build
```

### Without Docker

```bash
# 1. PostgreSQL 16 with pgvector, database aeo/aeo
# 2. Worker
cd nlp-worker && pip install -r requirements.txt   # optionally: -r requirements-ml.txt
DEMO_BASE_URL=http://localhost:8000/demo-sites uvicorn app.main:app --port 8000
# 3. Orchestrator (needs Maven Central)
cd orchestrator && mvn spring-boot:run
# 4. Dashboard (API_URL may point at the orchestrator or straight at the worker; unset = demo snapshot)
cd frontend && npm install && API_URL=http://localhost:8080 npm run dev
```

## Deploy the dashboard on Netlify

`netlify.toml` sits at the repository root and builds `frontend/` with the official Next.js runtime.
Netlify hosts the dashboard only; the worker, orchestrator and database are long-running services.

* **No backend yet:** leave `API_URL` unset. The site serves a bundled, read-only snapshot of real engine
  output (`frontend/lib/demo-snapshot.json`), so every section, chart, payload, ZIP download and the
  edge-case proof work with no errors. Actions that need computation (scraping, filing claims, scoring a
  custom question) explain that the demo is read-only.
* **Live backend:** run `docker compose up` on any host (Render, Railway, a VM), then set `API_URL` in
  Netlify (Site configuration, Environment variables) to the orchestrator's public URL, for example
  `https://aeo-api.example.com`, and redeploy. `/api/*` is then proxied at runtime.
* **Refresh the snapshot** after changing the demo data: `cd frontend && node scripts/snapshot.mjs http://localhost:8000`.

Only the `main` branch builds; the `ignore` rule in `netlify.toml` skips other branches and pull requests.

## How each requirement is met

| Spec | Implementation | Where |
|---|---|---|
| Req 1.1 extraction loss | Every page is read twice: raw HTML as a non-JS crawler sees it, and rendered (Playwright, or an XHR interceptor that discovers `fetch()` endpoints and captures their JSON). Extraction loss = share of decision facts only visible after rendering. | `nlp-worker/app/scraper.py` |
| Req 1.2 Machine Hubs | `/institutional-data/` flat Markdown per product, `financial-facts.json`, `schema.jsonld`, `llms.txt`, downloadable ZIP. Pure functions of graph state, byte-identical across runs. | `app/payloads.py` |
| Req 2.1 Corroboration Deficit | Claims are nodes with `valid_from`/`valid_to`. Naive mass = 1 + ln(1 + links) per claim (an LLM's volume prior). Temporal mass multiplies authority, half-life decay and a 0.9 supersession penalty. Deficit = 1 − ground truth's naive share. | `app/graph.py` |
| Req 2.2 `replaces` versioning | Schema.org `FinancialProduct` nodes carry `replaces` with the superseded figure or discontinued product. | `app/payloads.py` |
| Req 3.1/3.2 Context Severance | Cosine distance between the query and the landing page on a hybrid dense + lexical vector; above 0.75 the engine emits a hydration script and text payload built from the best-matching page's facts. | `app/analytics.py` |
| Req 4.1/4.2 Sub-Entity Partitioning | Seeded 2-means over all text nodes anchored on Retail and Institutional prototypes; Semantic Dilution Index, attribute bleed, brand-level vs partitioned retrieval, Comparative Markdown Matrix with vector priorities. | `app/analytics.py`, `app/payloads.py` |
| ABSA tie-breaker | Simultaneous contradictory official figures: confidence = 0.55 legal/numeric syntax + 0.30 FinBERT neutral probability + 0.15 decimal precision. | `app/graph.py` |
| Zero-vector pages | Sparse pages trigger a crawl of linked SEBI/SEC filings. | `app/scraper.py` |
| Orchestration | Webhook ingestion with HMAC-SHA256, scheduled scrapes, durable job log, GraphQL + REST gateway on Java 21 virtual threads. | `orchestrator/` |
| Dashboard | Explorer (left), tabbed editor (center), Wire terminal (bottom), resizable with React-Reflex; Broadsheet light theme and the exact Darcula palette. | `frontend/` |

## The edge cases

Run them from the dashboard ("Run edge-case audit"), via `POST /api/validation/run`, or with pytest:

```bash
cd nlp-worker && pytest -q          # unit tests, plus the full suite when a seeded DB is reachable
```

All eight pass; the generated report is in [`docs/Risk_Validation_Report.md`](docs/Risk_Validation_Report.md)
and is also included in every Machine Hub ZIP.

1. Factual staleness: 10,000 forum posts say 2%, one page updated yesterday says 5%. Deficit 99.87%, GraphRAG answers 5%, `replaces` payload emitted.
2. Gated calculator: mortgage rates load via `fetch()`; raw HTML has none; the rate reaches the Markdown hub.
3. Context severance: "ESG funds with expense ratio < 0.5%" landing on the homepage scores above 0.75; hydration surfaces the ESG fund at 0.42%.
4. Semantic dilution: brand-wide retrieval answers 1.25% for the institutional fund, partitioned retrieval answers 0.45%.
5. Payload obfuscation: a quote API returns a base64 PDF; the JSON is captured, the blob discarded, APR 13.49% extracted.
6. Zero-vector page: a hero image and "Contact Sales" page falls back to its SEBI filing.
7. Contradictory ground truths: a 0.20% marketing tagline and a 0.35% legal disclaimer with the same timestamp; the disclaimer wins.
8. Determinism: hub files and ZIP are byte-identical across runs.

## API highlights

```
GET  /api/institutions/{slug}/overview          front-page metrics
POST /api/scrape                                {institution,url,entity?,namespace?}
POST /api/ingest/text                           file any text (forum, press, official) into the graph
GET  /api/entities/{id}/graph?attribute=yield   corroboration + timeline + versions
POST /api/severance                             {institution,query,landing_url?}
POST /api/institutions/{slug}/partition         namespaces, dilution, bleed
GET  /api/hubs/{slug}/institutional-data/index.md
GET  /api/hubs/{slug}/financial-facts.json | schema.jsonld | hydration.js?query= | export.zip
POST /api/webhooks/portal-update                (orchestrator) HMAC signed, see scripts/send-webhook.sh
GET  /api/orchestrator/jobs | schedules         (orchestrator)
```

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `NLP_MODE` | `auto` | `auto` loads FinBERT and sentence-transformers, falling back to lite encoders; `lite` never loads models |
| `RENDER_MODE` | `auto` | `auto` uses Playwright when installed, else the XHR interceptor |
| `HALF_LIFE_FORUM` / `HALF_LIFE_PRESS` | 90 / 180 days | timestamp decay |
| `SUPERSESSION_PENALTY` | 0.9 | weight removed from claims contradicting a newer filing |
| `SEVERANCE_THRESHOLD` | 0.75 | hydration trigger |
| `AEO_WEBHOOK_SECRET` | `change-me` | HMAC key for portal webhooks |

## Notes

* The demo institutions, URLs and figures are fictional and served by the worker itself, so the stack
  runs offline after the first build.
* Schema.org defines `replaces` on `UpdateAction`; it is emitted on `FinancialProduct` here because the
  specification requires that shape. `additionalProperty` carries the same facts in standard form.
* With real transformer embeddings the absolute severance scores shift; the hybrid dense + lexical
  vector keeps the 0.75 threshold meaningful, and `SEVERANCE_THRESHOLD` can be tuned per deployment.
