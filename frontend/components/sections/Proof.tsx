"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import CodeView from "../CodeView";
import { Failure, SectionHead } from "../Bits";
import { useAsync } from "@/lib/hooks";

export default function Proof() {
  const r = useAsync(() => api.validate(), []);
  const [open, setOpen] = useState<string | null>(null);
  if (r.error) return <Failure error={r.error} retry={r.reload} />;
  const d = r.data;
  return (
    <article className="max-w-[1000px]">
      <SectionHead term="QA edge cases, risk validation"
        title={d ? `${d.passed} of ${d.total} edge cases hold against live data` : "Running the edge cases against live data"}
        deck="Each case from the QA specification runs against the seeded temporal graph, not against mocks. A case passes only when every one of its checks does." />
      <div className="flex gap-3 mb-5">
        <button className="btn btn-solid" onClick={r.reload} disabled={r.loading}>{r.loading ? "Running…" : "Run again"}</button>
        <a className="btn" href={api.reportUrl()} target="_blank" rel="noreferrer">Open the report (Markdown)</a>
      </div>
      <ol className="border-t-2 border-ink">
        {(d?.results ?? []).map((c: any, i: number) => (
          <li key={c.id} className="border-b hairline py-3">
            <button className="w-full text-left flex items-baseline gap-4" onClick={() => setOpen(open === c.id ? null : c.id)} aria-expanded={open === c.id}>
              <span className="font-mono text-soft tabnum w-6">{i + 1}</span>
              <span className={`ui text-[13px] font-semibold w-12 ${c.passed ? "text-truth" : "text-alert"}`}>{c.passed ? "Pass" : "Fail"}</span>
              <span className="headline text-[20px] flex-1">it handles: {c.title.replace(/^(handles|bypasses|quantifies|prevents|mitigates|resolves|serves) /, "")}</span>
              <span className="font-mono text-[12px] text-soft tabnum">{c.ms} ms</span>
            </button>
            <ul className="ml-[88px] mt-2 space-y-0.5 text-[14.5px]">
              {Object.entries(c.checks).map(([k, v]) => (
                <li key={k}><span aria-hidden className={v ? "text-truth" : "text-alert"}>{v ? "✓" : "✗"}</span> {k}</li>
              ))}
              {c.error && <li className="text-alert font-mono text-[12px]">{c.error}</li>}
            </ul>
            {open === c.id && <div className="ml-[88px] mt-3"><CodeView lang="json" code={JSON.stringify({ metrics: c.metrics, evidence: c.evidence }, null, 2)} className="max-h-[340px]" /></div>}
          </li>
        ))}
      </ol>
    </article>
  );
}
