// Read-only demo backend: serves the captured snapshot (lib/demo-snapshot.json) when the
// dashboard is deployed without an API_URL, e.g. on Netlify. Refresh it with
// `node scripts/snapshot.mjs <api base>` against a running engine.
import snapshot from "./demo-snapshot.json";

type Entry = { status: number; type: string; text?: string; b64?: string; disposition?: string };
const S = snapshot as unknown as Record<string, Entry> & { __meta: { captured_at: string; suggestions: string[] } };

const READ_ONLY =
  "This deployment is a read-only demo snapshot. Connect the live engine (set API_URL) to scrape pages, file claims or score new questions.";

function send(e: Entry) {
  const headers: Record<string, string> = { "content-type": e.type };
  if (e.disposition) headers["content-disposition"] = e.disposition;
  const body = e.b64 != null ? Buffer.from(e.b64, "base64") : e.text ?? "";
  return new Response(body, { status: e.status, headers });
}

const json = (v: unknown, status = 200) => Response.json(v, { status });

export function demoResponse(method: string, path: string, search: string, body: string): Response {
  const meta = S.__meta;
  if (path === "health") {
    const h = JSON.parse(S["GET /health"].text!);
    return json({ ...h, demo: true, captured_at: meta.captured_at, suggestions: meta.suggestions });
  }
  if (path === "orchestrator/status") return json({ orchestrator: "demo", jobs: null });
  if (path === "orchestrator/jobs") return json([]);
  if (path === "logs") return search === "?after_id=0" ? send(S["GET /logs?after_id=0"]) : json([]);
  if (method === "POST" && path === "severance") {
    try {
      const b = JSON.parse(body || "{}");
      const hit = !b.landing_url && S[`POST /severance ${b.institution} ${b.query}`];
      if (hit) return send(hit);
    } catch { /* fall through to the read-only answer */ }
    return json({ detail: READ_ONLY, demo: true }, 409);
  }
  const hit = S[`${method} /${path}${search}`];
  if (hit) return send(hit);
  if (method !== "GET") return json({ detail: READ_ONLY, demo: true }, 409);
  return json({ detail: "Not part of the demo snapshot.", demo: true }, 404);
}
