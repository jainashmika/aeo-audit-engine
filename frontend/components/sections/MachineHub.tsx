"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { useStore } from "@/lib/store";
import CodeView from "../CodeView";
import Markdown from "../Markdown";
import { Failure, Loading, SectionHead } from "../Bits";

export default function MachineHub() {
  const { institution, hubPath, openHub } = useStore();
  const files = useAsync(() => api.manifest(institution), [institution]);
  const path = files.data?.some((f) => f.path === hubPath) ? hubPath : files.data?.[0]?.path ?? hubPath;
  const file = useAsync(() => api.hubFile(institution, path), [institution, path]);
  const [rendered, setRendered] = useState(true);
  const lang = path.endsWith(".json") || path.endsWith(".jsonld") ? "json" : path.endsWith(".md") ? "md" : "text";
  if (files.error) return <Failure error={files.error} retry={files.reload} />;
  const total = (files.data ?? []).reduce((a, f) => a + f.bytes, 0);

  return (
    <article className="max-w-[1180px]">
      <SectionHead term="Automated payload generators, /institutional-data/"
        title="The ground truth, rewritten for machines"
        deck="Flat Markdown, a financial-facts.json and Schema.org JSON-LD, all generated from the knowledge graph. Identical graph state always produces byte-identical files, so a crawler never sees two versions of the same fact." />
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <a className="btn btn-solid" href={api.zipUrl(institution)} download>Download the hub as ZIP</a>
        <a className="btn" href={api.reportUrl()} target="_blank" rel="noreferrer">Risk validation report</a>
        <span className="ui text-[13px] text-soft tabnum">{files.data?.length ?? 0} files, {(total / 1024).toFixed(1)} KB</span>
      </div>
      <div className="grid lg:grid-cols-[280px_1fr] gap-6">
        <ul className="font-mono text-[12.5px] border hairline bg-sheet/40 py-2 h-fit">
          {(files.data ?? []).map((f) => (
            <li key={f.path}>
              <button onClick={() => openHub(f.path)} className={`w-full text-left px-3 py-1 hover:bg-tint/70 ${f.path === path ? "bg-tint" : ""}`}>
                {f.path}
                <span className="block text-soft text-[11px]">{f.bytes} B, sha {f.sha256}</span>
              </button>
            </li>
          ))}
        </ul>
        <section className="min-w-0">
          <div className="flex items-center justify-between border-b hairline pb-1 mb-2">
            <span className="font-mono text-[13px]">{path}</span>
            {lang === "md" && (
              <button className="ui text-[13px] underline underline-offset-2" onClick={() => setRendered(!rendered)}>
                {rendered ? "Show source" : "Show rendered"}
              </button>
            )}
          </div>
          {!file.data ? <Loading /> : lang === "md" && rendered
            ? <div className="max-w-[78ch]"><Markdown src={file.data} /></div>
            : <CodeView lang={lang as any} code={file.data} className="max-h-[62vh]" />}
        </section>
      </div>
    </article>
  );
}
