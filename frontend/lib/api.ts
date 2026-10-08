/* Thin typed-ish client for the AEO API. All calls are same-origin (/api) and proxied. */
export class ApiError extends Error {}

async function req<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { cache: "no-store", ...init });
  const ct = res.headers.get("content-type") || "";
  const body = ct.includes("json") ? await res.json() : await res.text();
  if (!res.ok) throw new ApiError(typeof body === "string" ? body : body?.detail ?? `HTTP ${res.status}`);
  return body as T;
}

const post = <T = any>(path: string, data?: unknown) =>
  req<T>(path, { method: "POST", headers: { "content-type": "application/json" }, body: data ? JSON.stringify(data) : undefined });

export const api = {
  health: () => req("/health"),
  orchestrator: () => req("/orchestrator/status").catch(() => null),
  jobs: () => req<any[]>("/orchestrator/jobs?limit=12").catch(() => []),
  institutions: () => req<any[]>("/institutions"),
  entities: (slug: string) => req<any[]>(`/institutions/${slug}/entities`),
  overview: (slug: string) => req(`/institutions/${slug}/overview`),
  scrapes: (slug: string) => req<any[]>(`/institutions/${slug}/scrapes`),
  scrape: (institution: string, url: string, entity?: string, namespace?: string) =>
    post("/scrape", { institution, url, entity: entity || null, namespace: namespace || null }),
  graph: (entityId: string, attribute: string) =>
    req(`/entities/${entityId}/graph?attribute=${encodeURIComponent(attribute)}`),
  texts: (entityId: string) => req<any[]>(`/entities/${entityId}/texts?limit=12`),
  ingestText: (b: any) => post("/ingest/text", b),
  severance: (institution: string, query: string, landing_url?: string) =>
    post("/severance", { institution, query, landing_url: landing_url || null }),
  severanceHistory: (slug: string) => req<any[]>(`/institutions/${slug}/severance`),
  partition: (slug: string) => post(`/institutions/${slug}/partition`),
  namespaced: (slug: string, entity: string, attribute: string) =>
    req(`/institutions/${slug}/namespaced-answer?entity=${entity}&attribute=${attribute}`),
  manifest: (slug: string) => req<any[]>(`/hubs/${slug}/manifest`),
  hubFile: (slug: string, path: string) => req<string>(`/hubs/${slug}/file?path=${encodeURIComponent(path)}`)
    .then((b) => (typeof b === "string" ? b : JSON.stringify(b, null, 2))),
  zipUrl: (slug: string) => `/api/hubs/${slug}/export.zip`,
  reportUrl: () => `/api/validation/report.md`,
  validate: () => post("/validation/run"),
  logs: (after: number) => req<any[]>(`/logs?after_id=${after}`),
};
