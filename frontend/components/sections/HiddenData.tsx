"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { attrLabel, pct, shortUrl, val } from "@/lib/format";
import { useAsync } from "@/lib/hooks";
import { useStore } from "@/lib/store";
import CodeView from "../CodeView";
import { Bars, Failure, Loading, Pill, SectionHead } from "../Bits";

export default function HiddenData() {
  const { institution, scrapeUrl, openScrape, bump } = useStore();
  const sc = useAsync(() => api.scrapes(institution), [institution]);
  if (sc.error) return <Failure error={sc.error} retry={sc.reload} />;
  if (!sc.data) return <Loading what="Reading the crawl log" />;
  const rows = sc.data;
  const sel = rows.find((r) => r.url === scrapeUrl) ?? rows[0];
  const hidden = rows.filter((r) => r.extraction_loss > 0).length;

  return (
    <article className="max-w-[1180px]">
      <SectionHead term="Vector sparsity, extraction loss"
        title={`${hidden} of ${rows.length} pages hide facts from AI crawlers`}
        deck="Each page is read twice: once as raw HTML, the way most answer-engine crawlers see it, and once after the page's scripts run. Whatever only appears the second time is invisible to the model." />
      <div className="grid lg:grid-cols-[minmax(0,420px)_1fr] gap-8">
        <section>
          <table className="ledger w-full text-[13.5px] tabnum">
            <thead><tr><th>Page</th><th>Facts seen raw</th><th>Loss</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} onClick={() => openScrape(r.url)} className={`cursor-pointer ${sel?.url === r.url ? "bg-tint" : ""}`}>
                  <td className="font-mono text-[12px] break-all">
                    <button className="text-left hover:underline" onClick={() => openScrape(r.url)}>{shortUrl(r.url)}</button>
                  </td>
                  <td className="font-mono">{r.static_facts} / {r.rendered_facts}</td>
                  <td className={`font-mono ${r.extraction_loss > 0.5 ? "text-alert" : ""}`}>{pct(r.extraction_loss, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <ScrapeForm institution={institution} onDone={(u) => { sc.reload(); openScrape(u); bump(); }} />
        </section>
        {sel && <Detail s={sel} />}
      </div>
    </article>
  );
}

function Detail({ s }: { s: any }) {
  const d = s.details;
  const lostKeys = new Set(d.lost_facts.map((f: any) => `${f.attribute}:${f.value}`));
  return (
    <section>
      <div className="flex flex-wrap items-baseline gap-3 mb-3">
        <h3 className="headline text-2xl">{d.title || shortUrl(s.url)}</h3>
        <Pill ok={s.extraction_loss === 0}>{s.render_mode}</Pill>
        {d.zero_vector_fallback && <Pill ok={false}>sparse page, filings crawled</Pill>}
      </div>
      <Bars rows={[
        { label: "Tokens a plain-text crawler reads", value: s.rendered_tokens ? s.static_tokens / s.rendered_tokens : 0, tone: "soft", note: `${s.static_tokens} of ${s.rendered_tokens}` },
        { label: "Decision facts lost without rendering", value: s.extraction_loss, tone: s.extraction_loss > 0.5 ? "alert" : "truth", note: pct(s.extraction_loss, 0) },
      ]} />
      <div className="grid md:grid-cols-2 gap-6 mt-5">
        <div>
          <p className="ui text-[13px] font-semibold mb-1">What a crawler reads</p>
          <p className="text-[14px] leading-relaxed text-soft border-t hairline pt-2">{d.static_excerpt || "Nothing but navigation."}</p>
        </div>
        <div>
          <p className="ui text-[13px] font-semibold mb-1">What a person sees</p>
          <p className="text-[14px] leading-relaxed border-t hairline pt-2">{d.rendered_excerpt}</p>
        </div>
      </div>
      <h4 className="ui text-[13px] font-semibold mt-6 mb-1">Facts recovered for the Machine Hub</h4>
      <table className="ledger w-full text-[13.5px] tabnum">
        <thead><tr><th>Attribute</th><th>Value</th><th>Found in</th><th>Visible raw</th></tr></thead>
        <tbody>
          {[...d.rendered_facts, ...d.filing_facts].map((f: any, i: number) => (
            <tr key={i}>
              <td>{attrLabel(f.attribute)}{f.product_hint ? <span className="text-soft">, {f.product_hint}</span> : null}</td>
              <td className="font-mono">{val(f.value, f.unit)}</td>
              <td className="ui text-[12.5px] text-soft">{f.meta?.json_path ? `XHR ${f.meta.json_path}` : i >= d.rendered_facts.length ? "linked filing" : "page text"}</td>
              <td>{lostKeys.has(`${f.attribute}:${f.value}`) ? <Pill ok={false}>no</Pill> : <Pill ok>yes</Pill>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {d.intercepted.length > 0 && <>
        <h4 className="ui text-[13px] font-semibold mt-6 mb-1">Intercepted network responses (binary blobs removed)</h4>
        <CodeView lang="json" code={JSON.stringify(d.intercepted, null, 2)} className="max-h-[260px]" />
      </>}
      {d.filings.length > 0 && <p className="text-[14px] mt-4">Fallback crawl: {d.filings.map((f: any) => shortUrl(f.url)).join(", ")}.</p>}
    </section>
  );
}

function ScrapeForm({ institution, onDone }: { institution: string; onDone: (u: string) => void }) {
  const [url, setUrl] = useState("");
  const [entity, setEntity] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const ents = useAsync(() => api.entities(institution), [institution]);
  const demo = useStore((s) => s.demo);
  if (demo) return <p className="ui text-[13px] text-soft border-t hairline pt-3 mt-6">This demo is a read-only snapshot. Connect the live engine (set <span className="font-mono">API_URL</span>) to scrape new pages.</p>;
  return (
    <form className="mt-6 border-t hairline pt-3" onSubmit={async (e) => {
      e.preventDefault(); setBusy(true); setMsg(null);
      try {
        const r = await api.scrape(institution, url, entity || undefined);
        setMsg(`Scraped with ${r.render_mode}: extraction loss ${pct(r.extraction_loss, 0)}, ${r.claims_created} claims added.`);
        onDone(url);
      } catch (err: any) { setMsg(`Scrape failed: ${err.message}`); } finally { setBusy(false); }
    }}>
      <p className="ui text-[13px] font-semibold mb-1">Scrape another page</p>
      <input className="field" type="url" required placeholder="https://..." value={url} onChange={(e) => setUrl(e.target.value)} aria-label="Page URL" />
      <select className="field mt-2" value={entity} onChange={(e) => setEntity(e.target.value)} aria-label="Attach facts to product">
        <option value="">Attach facts to the product named on the page</option>
        {(ents.data ?? []).map((e) => <option key={e.slug} value={e.slug}>{e.entity_name}</option>)}
      </select>
      <button className="btn btn-solid mt-2" disabled={busy}>{busy ? "Scraping…" : "Scrape page"}</button>
      {msg && <p className="ui text-[13px] mt-2">{msg}</p>}
    </form>
  );
}
