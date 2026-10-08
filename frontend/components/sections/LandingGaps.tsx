"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { day, shortUrl } from "@/lib/format";
import { useAsync } from "@/lib/hooks";
import { useStore } from "@/lib/store";
import CodeView from "../CodeView";
import Markdown from "../Markdown";
import { Failure, Pill, SectionHead } from "../Bits";

const SUGGEST = ["ESG funds with expense ratio < 0.5%", "tax-advantaged retirement accounts in India",
  "home loan interest rate", "institutional quant mandate for corporate treasury", "high dividend yield ETF India"];

function Gauge({ v, threshold }: { v: number; threshold: number }) {
  const a = (x: number) => Math.PI * (1 - Math.min(1, Math.max(0, x)));
  const pt = (x: number, r: number) => [100 + r * Math.cos(a(x)), 100 - r * Math.sin(a(x))];
  const [x1, y1] = pt(v, 80);
  const [t1, t2] = [pt(threshold, 70), pt(threshold, 92)];
  const over = v > threshold;
  return (
    <svg viewBox="0 0 200 116" className="w-full max-w-[300px]" role="img" aria-label={`Context severance ${v.toFixed(2)}, threshold ${threshold}`}>
      <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="rgb(var(--rule))" strokeWidth="14" />
      <path d={`M 20 100 A 80 80 0 0 1 ${x1} ${y1}`} fill="none" stroke={over ? "rgb(var(--alert))" : "rgb(var(--truth))"} strokeWidth="14" />
      <line x1={t1[0]} y1={t1[1]} x2={t2[0]} y2={t2[1]} stroke="rgb(var(--ink))" strokeWidth="2" />
      <text x="100" y="92" textAnchor="middle" className="headline" fontSize="30" fill="rgb(var(--ink))">{v.toFixed(3)}</text>
      <text x="100" y="112" textAnchor="middle" fontSize="9" fill="rgb(var(--soft))" fontFamily="var(--font-ui)">hydrate above {threshold}</text>
    </svg>
  );
}

export default function LandingGaps() {
  const { institution, bump, demo } = useStore();
  const pages = useAsync(() => api.scrapes(institution), [institution]);
  const hist = useAsync(() => api.severanceHistory(institution), [institution]);
  const [q, setQ] = useState(SUGGEST[0]);
  const [landing, setLanding] = useState("");
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState<"preview" | "script" | "text">("preview");

  const run = async (query = q) => {
    if (demo && (landing || !SUGGEST.includes(query))) {
      setErr(null);
      setNote("This demo is a read-only snapshot, so only the suggested questions on the homepage are scored. Connect the live engine (set API_URL) to score any question against any page.");
      return;
    }
    setNote(null);
    setBusy(true); setErr(null);
    try { setRes(await api.severance(institution, query, landing || undefined)); hist.reload(); bump(); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setRes(null); run(SUGGEST[0]); }, [institution]);

  return (
    <article className="max-w-[1180px]">
      <SectionHead term="Context Severance Score, contextual UI hydration"
        title="Where does an AI-referred visitor land, and how far is it from what they asked?"
        deck="A visitor arrives from ChatGPT or Perplexity with a specific question. The score is the cosine distance between that question and the page they land on; above 0.75 the engine writes a script that brings the right facts to them." />
      <form className="grid md:grid-cols-[1fr_280px_auto] gap-2 items-end" onSubmit={(e) => { e.preventDefault(); run(); }}>
        <label className="block"><span className="ui text-[13px] text-soft">Question asked in the AI assistant</span>
          <input className="field mt-1" value={q} onChange={(e) => setQ(e.target.value)} required /></label>
        <label className="block"><span className="ui text-[13px] text-soft">Landing page</span>
          <select className="field mt-1" value={landing} onChange={(e) => setLanding(e.target.value)}>
            <option value="">Homepage</option>
            {(pages.data ?? []).map((p) => <option key={p.url} value={p.url}>{shortUrl(p.url)}</option>)}
          </select></label>
        <button className="btn btn-solid h-[38px]" disabled={busy}>{busy ? "Scoring…" : "Score the landing"}</button>
      </form>
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 ui text-[13px]">
        {SUGGEST.map((s) => <button key={s} className="text-soft hover:text-ink underline-offset-2 hover:underline" onClick={() => { setQ(s); run(s); }}>{s}</button>)}
      </div>
      {note && <p className="ui text-[13.5px] mt-3 border-l-2 border-accent pl-3">{note}</p>}
      {err && <Failure error={err} />}
      {res && (
        <div className="grid lg:grid-cols-[320px_1fr] gap-8 mt-6">
          <section>
            <Gauge v={res.context_severance_score} threshold={res.threshold} />
            <p className="text-[15px] mt-2 leading-relaxed">
              Landing on <span className="font-mono text-[13px]">{shortUrl(res.landing_url)}</span>{" "}
              {res.hydrate ? "severs the context. Hydration is triggered." : "keeps the context. No hydration needed."}
            </p>
            <h4 className="ui text-[13px] font-semibold mt-5 mb-1">Distance from the question, every page</h4>
            <ul className="space-y-1">
              {res.ranking.map((r: any) => (
                <li key={r.url} className="text-[13px]">
                  <div className="flex justify-between gap-2"><span className="font-mono text-[11.5px] truncate">{shortUrl(r.url)}</span><span className="font-mono tabnum">{r.distance.toFixed(3)}</span></div>
                  <div className="h-1.5 bg-rule/40"><div className={`h-full ${r.url === res.landing_url ? "bg-alert" : r.url === res.best_match.url ? "bg-truth" : "bg-soft/60"}`} style={{ width: `${r.distance * 100}%` }} /></div>
                </li>
              ))}
            </ul>
            <p className="ui text-[12px] text-soft mt-2">Detected intents: {res.intents.map((i: any) => i.intent.replace("_", " ")).join(", ")}.</p>
          </section>
          <section>
            <div className="flex items-baseline justify-between border-b hairline mb-3">
              <h3 className="headline text-2xl">Hydration payload</h3>
              <div className="flex ui text-[13px] gap-3" role="tablist">
                {(["preview", "script", "text"] as const).map((v) => (
                  <button key={v} role="tab" aria-selected={view === v} onClick={() => setView(v)}
                    className={`pb-1 ${view === v ? "border-b-2 border-alert text-ink" : "text-soft"}`}>{v === "preview" ? "Visitor preview" : v === "script" ? "Script" : "Text payload"}</button>
                ))}
              </div>
            </div>
            {!res.hydration && <p className="text-soft">The landing page already answers the question, so no payload is generated.</p>}
            {res.hydration && view === "preview" && (
              <div className="relative h-[380px] border hairline bg-white/60 overflow-hidden">
                <div className="p-5 opacity-40 text-[13px] font-sans text-[#333]">
                  <div className="h-6 w-40 bg-[#0b3d6e] mb-4" />
                  <div className="h-16 bg-[#1d6fb8]/40 mb-3" />
                  <div className="h-3 w-3/4 bg-[#999]/40 mb-2" /><div className="h-3 w-2/3 bg-[#999]/40 mb-2" /><div className="h-3 w-1/2 bg-[#999]/40" />
                </div>
                <aside className="absolute right-4 top-6 max-h-[340px] overflow-auto max-w-[340px] bg-[#fffaf2] text-[#191714] border border-[#191714] p-4 text-[14px] leading-snug" style={{ boxShadow: "6px 6px 0 #F3A693", fontFamily: "Georgia, serif" }}>
                  <div className="text-[11px] font-mono text-[#5E574C]">You asked</div>
                  <div className="italic mb-2">{res.query}</div>
                  <ul className="list-disc pl-4">{res.hydration.facts.map((f: any, i: number) => <li key={i}><b>{f.entity}</b>: {f.attribute.replace("_", " ")} {f.display} <small>(as of {day(f.valid_from)})</small></li>)}</ul>
                  <span className="inline-block mt-2 text-[#9E2B3A] underline">{res.hydration.headline}</span>
                </aside>
              </div>
            )}
            {res.hydration && view === "script" && <CodeView lang="js" code={res.hydration.script} className="max-h-[360px]" />}
            {res.hydration && view === "text" && <div className="border hairline p-4"><Markdown src={res.hydration.markdown} /></div>}
            {res.hydration && <p className="ui text-[12.5px] text-soft mt-2">Install with a script tag pointing at <span className="font-mono">/api/hubs/{institution}/hydration.js?query=…</span>. It only runs for visitors referred by an AI assistant.</p>}
          </section>
        </div>
      )}
      <h3 className="ui text-[14px] font-semibold mt-8 mb-1">Recent referral simulations</h3>
      <table className="ledger w-full text-[13.5px] tabnum">
        <thead><tr><th>Question</th><th>Severance</th><th>Best page</th><th>Hydrate</th></tr></thead>
        <tbody>
          {(hist.data ?? []).slice(0, 8).map((h, i) => (
            <tr key={i}><td>{h.query}</td><td className="font-mono">{h.severance_score.toFixed(3)}</td>
              <td className="font-mono text-[12px]">{shortUrl(h.best_match_url)}</td><td><Pill ok={!h.hydrate}>{h.hydrate ? "yes" : "no"}</Pill></td></tr>
          ))}
        </tbody>
      </table>
    </article>
  );
}
