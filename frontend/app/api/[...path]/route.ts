// Runtime proxy. The browser always calls /api/* on the dashboard origin.
//  * API_URL set   -> forward to the orchestration API (or straight to the NLP worker).
//  * API_URL unset -> answer from the bundled read-only demo snapshot (Netlify without a backend).
import { NextRequest } from "next/server";
import { demoResponse } from "@/lib/demo";

export const dynamic = "force-dynamic";
const PASS = ["content-type", "content-disposition"];

async function handle(req: NextRequest, { params }: { params: { path: string[] } }) {
  const apiUrl = (process.env.API_URL || "").replace(/\/+$/, "");
  const path = params.path.join("/");
  const body = ["GET", "HEAD"].includes(req.method) ? "" : await req.text();
  if (!apiUrl) return demoResponse(req.method, path, req.nextUrl.search, body);

  const target = `${apiUrl}/api/${params.path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const headers: Record<string, string> = {};
  const ct = req.headers.get("content-type");
  if (ct) headers["content-type"] = ct;
  try {
    const res = await fetch(target, { method: req.method, headers, body: body || undefined, cache: "no-store" });
    const out = new Headers();
    PASS.forEach((h) => res.headers.get(h) && out.set(h, res.headers.get(h)!));
    return new Response(await res.arrayBuffer(), { status: res.status, headers: out });
  } catch {
    return Response.json({ detail: `The engine is unreachable at ${apiUrl}.` }, { status: 502 });
  }
}

export { handle as GET, handle as POST, handle as PATCH, handle as PUT, handle as DELETE };
