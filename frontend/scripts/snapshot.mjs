#!/usr/bin/env node
/**
 * Capture a read-only snapshot of every API response the dashboard needs, from a running
 * backend, into lib/demo-snapshot.json. The Netlify deployment serves this snapshot when no
 * API_URL is configured, so the site works with no backend at all.
 *
 *   node scripts/snapshot.mjs http://localhost:8000      (worker)  or  http://localhost:8080 (orchestrator)
 */
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const BASE = (process.argv[2] || "http://localhost:8000").replace(/\/+$/, "") + "/api";
const OUT = join(dirname(fileURLToPath(import.meta.url)), "..", "lib", "demo-snapshot.json");
const SUGGEST = ["ESG funds with expense ratio < 0.5%", "tax-advantaged retirement accounts in India",
  "home loan interest rate", "institutional quant mandate for corporate treasury", "high dividend yield ETF India"];

const snap = {};
async function grab(method, path, body, key) {
  const res = await fetch(BASE + path, {
    method, headers: body ? { "content-type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined,
  });
  const ct = res.headers.get("content-type") || "application/json";
  const disp = res.headers.get("content-disposition");
  const buf = Buffer.from(await res.arrayBuffer());
  const binary = !/json|text|javascript|markdown/.test(ct);
  snap[key ?? `${method} ${path}`] = {
    status: res.status, type: ct, ...(disp ? { disposition: disp } : {}),
    ...(binary ? { b64: buf.toString("base64") } : { text: buf.toString("utf8") }),
  };
  if (!res.ok) console.warn(`  ${res.status} ${method} ${path}`);
  return binary ? null : ct.includes("json") ? JSON.parse(buf.toString("utf8")) : buf.toString("utf8");
}

const enc = encodeURIComponent;
console.log(`snapshotting ${BASE}`);
await grab("GET", "/health");
await grab("POST", "/validation/run");
await grab("GET", "/validation/report.md");
const insts = await grab("GET", "/institutions");
for (const { slug } of insts) {
  console.log(`  ${slug}`);
  const ents = await grab("GET", `/institutions/${slug}/entities`);
  await grab("GET", `/institutions/${slug}/overview`);
  await grab("GET", `/institutions/${slug}/scrapes`);
  await grab("POST", `/institutions/${slug}/partition`);
  for (const q of SUGGEST) await grab("POST", "/severance", { institution: slug, query: q, landing_url: null }, `POST /severance ${slug} ${q}`);
  await grab("GET", `/institutions/${slug}/severance`);
  const files = await grab("GET", `/hubs/${slug}/manifest`);
  for (const f of files) await grab("GET", `/hubs/${slug}/file?path=${enc(f.path)}`);
  await grab("GET", `/hubs/${slug}/export.zip`);
  for (const e of ents) {
    if (!e.attributes.length) continue;
    await grab("GET", `/entities/${e.id}/texts?limit=12`);
    for (const a of e.attributes) await grab("GET", `/entities/${e.id}/graph?attribute=${enc(a)}`);
    if (e.namespace_type === "Institutional" && e.entity_kind === "product" && e.attributes.includes("expense_ratio"))
      await grab("GET", `/institutions/${slug}/namespaced-answer?entity=${e.slug}&attribute=expense_ratio`);
  }
}
const logs = await grab("GET", "/logs?after_id=0");
snap["GET /logs?after_id=0"].text = JSON.stringify(logs.slice(-60));
// Public demo: present the fictional banks under their own domains instead of the local worker URL
for (const v of Object.values(snap)) {
  if (v.text) v.text = v.text.replace(/https?:\/\/[^/"\s]+\/demo-sites\/(meridian|kaveri)\//g, (_, b) => `https://${b}.example/`);
}
snap.__meta = { captured_at: new Date().toISOString(), source: BASE, suggestions: SUGGEST };
writeFileSync(OUT, JSON.stringify(snap));
console.log(`wrote ${Object.keys(snap).length} responses, ${(JSON.stringify(snap).length / 1024).toFixed(0)} KB -> ${OUT}`);
