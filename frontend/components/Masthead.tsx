"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { useStore } from "@/lib/store";

export default function Masthead() {
  const { theme, setTheme, institution, setInstitution, go, bump } = useStore();
  const insts = useAsync(() => api.institutions(), []);
  const health = useAsync(() => api.health(), []);
  const [busy, setBusy] = useState(false);
  const today = new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const instName = insts.data?.find((i) => i.slug === institution)?.name ?? institution;
  const nlp = health.data?.nlp;

  const runAudit = () => {
    setBusy(true);
    go("proof");
    bump();
    setTimeout(() => setBusy(false), 1500);
  };

  const controls = (
    <div className="flex flex-wrap items-center gap-2 ui">
      <label className="sr-only" htmlFor="inst">Institution</label>
      <select id="inst" value={institution} onChange={(e) => setInstitution(e.target.value)}
        className="btn pr-6 cursor-pointer">
        {(insts.data ?? [{ slug: institution, name: institution }]).map((i) => (
          <option key={i.slug} value={i.slug}>{i.name}</option>
        ))}
      </select>
      <div role="radiogroup" aria-label="Theme" className="flex">
        {(["broadsheet", "darcula"] as const).map((t) => (
          <button key={t} role="radio" aria-checked={theme === t} onClick={() => setTheme(t)}
            className={`btn -ml-px first:ml-0 ${theme === t ? "btn-solid" : ""}`}>
            {t === "broadsheet" ? "Broadsheet" : "Darcula"}
          </button>
        ))}
      </div>
      <button className="btn btn-solid" onClick={runAudit} disabled={busy}>
        {busy ? "Auditing…" : "Run edge-case audit"}
      </button>
    </div>
  );

  if (theme === "darcula") {
    return (
      <header className="bg-sheet border-b hairline px-4 py-2 flex items-center justify-between gap-4">
        <div className="font-mono text-[13px]">
          <span className="text-kw">class</span> <span className="text-fn">AEOAuditEngine</span>
          <span className="text-soft"> {"// "}{instName}, {health.data?.demo ? "demo snapshot (read-only)" : nlp ? `nlp=${nlp.mode}` : "connecting"}</span>
        </div>
        {controls}
      </header>
    );
  }

  return (
    <header className="px-6 pt-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="headline text-[44px] leading-none font-[650] tracking-tight">The Answer-Engine Ledger</h1>
          <p className="italic text-soft mt-1 text-[15px]">
            What AI assistants say about {instName}, checked against what {instName} actually publishes.
          </p>
        </div>
        {controls}
      </div>
      <div className="double-rule mt-3" />
      <div className="flex justify-between text-[13px] ui text-soft py-1 border-b hairline">
        <span>{today}, Bengaluru edition</span>
        <span>{health.data?.demo
          ? `Read-only demo snapshot from ${new Date(health.data.captured_at).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}`
          : nlp ? `Language models: ${nlp.embedding}; ${nlp.sentiment}` : "Connecting to the analysis service"}</span>
      </div>
    </header>
  );
}
