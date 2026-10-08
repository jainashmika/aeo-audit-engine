"use client";
import { useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { attrLabel, day, num, pct, shortUrl, val } from "@/lib/format";
import { useAsync, usePalette } from "@/lib/hooks";
import { useStore } from "@/lib/store";
import CodeView from "../CodeView";
import { Failure, Loading, Pill, SectionHead } from "../Bits";

export default function StaleFacts() {
  const { institution, focus, setFocus, bump } = useStore();
  const ov = useAsync(() => api.overview(institution), [institution]);
  const lead = useMemo(() => {
    const s = [...(ov.data?.staleness ?? [])].sort((a: any, b: any) => b.corroboration_deficit - a.corroboration_deficit)[0];
    return s ? { entityId: s.entity_id, entityName: s.entity, attribute: s.attribute } : null;
  }, [ov.data]);
  const f = focus ?? lead;
  const g = useAsync(() => (f ? api.graph(f.entityId, f.attribute) : Promise.resolve(null)), [f?.entityId, f?.attribute]);
  const texts = useAsync(() => (f ? api.texts(f.entityId) : Promise.resolve([])), [f?.entityId]);
  const schema = useAsync(() => api.hubFile(institution, "schema.jsonld").then((s) => JSON.parse(s)), [institution]);
  const pal = usePalette();

  if (!f) return ov.loading ? <Loading /> : <p className="text-soft">Pick a product attribute in the index.</p>;
  if (g.error) return <Failure error={g.error} retry={g.reload} />;
  if (!g.data) return <Loading what="Weighing the evidence" />;
  const c = g.data.corroboration;
  const gt = c.ground_truth;
  const wrong = gt && c.naive_llm_answer !== gt.value;
  const node = schema.data?.["@graph"]?.find((n: any) => n.name === f.entityName);
  const series: string[] = g.data.timeline.series;
  const colors = [pal.alert, pal.truth, pal.num, pal.fn, pal.kw, pal.soft];
  const colorFor = (v: string) => (gt && +v === +gt.value.toFixed(2) ? pal.truth : colors[series.indexOf(v) % colors.length] === pal.truth ? pal.num : colors[series.indexOf(v) % colors.length]);

  return (
    <article className="max-w-[1180px]">
      <SectionHead term="Corroboration Deficit, temporal knowledge graph"
        title={wrong ? `Correction: the ${f.entityName} ${attrLabel(f.attribute).toLowerCase()} is ${val(gt.value, gt.unit)}, not ${val(c.naive_llm_answer, gt.unit)}`
          : `${f.entityName}: ${attrLabel(f.attribute).toLowerCase()} ${gt ? val(gt.value, gt.unit) : "has no official figure yet"}`}
        deck={gt ? <>Official since {day(gt.valid_from)} from {shortUrl(gt.source_url)}. {num(c.claims)} claims on record, {num(c.stale_claims)} of them contradict the current filing.</> : undefined} />

      <div className="grid lg:grid-cols-[1fr_340px] gap-8">
        <section>
          <h3 className="ui text-[14px] font-semibold mb-1">How the narrative mutated over time</h3>
          <p className="text-[14px] text-soft mb-2">Claim volume per value, weighted by inbound links. Vertical rules mark official publications.</p>
          <div className="h-[280px] border hairline bg-paper/50">
            <ResponsiveContainer>
              <AreaChart data={g.data.timeline.points} margin={{ top: 12, right: 16, bottom: 4, left: 0 }}>
                <CartesianGrid stroke={pal.rule} strokeDasharray="2 4" vertical={false} />
                <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} scale="time" tick={{ fontSize: 11, fill: pal.soft }}
                  tickFormatter={(t) => new Date(t).toLocaleDateString("en-IN", { month: "short", year: "2-digit" })} stroke={pal.rule} />
                <YAxis tick={{ fontSize: 11, fill: pal.soft }} stroke={pal.rule} width={44} />
                <Tooltip contentStyle={{ background: pal.paper, border: `1px solid ${pal.ink}`, fontSize: 12 }}
                  labelFormatter={(t) => new Date(t as number).toLocaleDateString("en-IN")} formatter={(v: any, n: any) => [Number(v).toFixed(1), `${n}%`]} />
                {series.map((s) => (
                  <Area key={s} type="monotone" dataKey={s} stackId="1" stroke={colorFor(s)} fill={colorFor(s)} fillOpacity={0.35} isAnimationActive={false} />
                ))}
                {g.data.timeline.official.map((o: any, i: number) => (
                  <ReferenceLine key={i} x={o.t} stroke={pal.ink} strokeDasharray="4 3"
                    label={{ value: `${o.value}%`, position: "insideTopRight", fill: pal.ink, fontSize: 11 }} />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <h3 className="ui text-[14px] font-semibold mt-6 mb-1">Value clusters, before and after re-weighting</h3>
          <table className="ledger w-full text-[14px] tabnum">
            <thead><tr><th>Value</th><th>Claims</th><th>Sources</th><th>Share as a model weighs it</th><th>Share after temporal weighting</th></tr></thead>
            <tbody>
              {c.clusters.map((k: any) => (
                <tr key={k.value}>
                  <td className="font-mono">{val(k.value, gt?.unit)} {gt && Math.abs(k.value - gt.value) < 0.05 && <Pill ok>filing</Pill>}</td>
                  <td>{num(k.claims)}</td>
                  <td className="ui text-[12.5px] text-soft">{Object.entries(k.sources).map(([s, n]) => `${s.replace("_", " ")} ${num(n as number)}`).join(", ")}</td>
                  <td className="font-mono">{pct(k.naive_share, 2)}</td>
                  <td className="font-mono">{pct(k.temporal_share, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3 className="ui text-[14px] font-semibold mt-6 mb-2">Most-linked text in the record</h3>
          <ul className="space-y-2">
            {(texts.data ?? []).slice(0, 6).map((t: any, i: number) => {
              const s = t.sentiment;
              const pol = s ? s.positive - s.negative : 0;
              return (
                <li key={i} className="border-l-2 pl-3 text-[15px] leading-snug" style={{ borderColor: t.source_type.startsWith("institutional") ? pal.truth : pal.accent }}>
                  “{t.content.slice(0, 220)}”
                  <span className="block ui text-[12px] text-soft mt-0.5 tabnum">
                    {t.source_type.replace("_", " ")}, {day(t.valid_from)}, {num(t.link_count)} links, sentiment {pol >= 0 ? "+" : ""}{pol.toFixed(2)}
                    {t.valid_to ? ", superseded" : ""}
                  </span>
                </li>);
            })}
          </ul>
        </section>

        <aside className="space-y-6">
          <div className="border hairline p-4 bg-sheet/50">
            <p className="ui text-[13px] text-soft">Corroboration Deficit</p>
            <p className={`headline text-[52px] leading-none tabnum ${c.corroboration_deficit > 0.5 ? "text-alert" : "text-truth"}`}>{pct(c.corroboration_deficit, 2)}</p>
            <dl className="ui text-[13px] mt-3 grid grid-cols-[1fr_auto] gap-y-1 tabnum">
              <dt className="text-soft">Naive model answer</dt><dd className="font-mono">{val(c.naive_llm_answer, gt?.unit)}</dd>
              <dt className="text-soft">GraphRAG answer</dt><dd className="font-mono">{val(c.graphrag_answer, gt?.unit)}</dd>
              <dt className="text-soft">Retail sentiment</dt><dd className="font-mono">{c.retail_sentiment == null ? "n/a" : c.retail_sentiment.toFixed(2)}</dd>
              <dt className="text-soft">Penalised mass</dt><dd className="font-mono">{num(Math.round(c.penalty_mass))}</dd>
            </dl>
            {c.hallucination_prevented && <p className="mt-3 text-[14px] text-truth">Temporal weighting flips the answer to the filed figure.</p>}
          </div>
          {node && (
            <div>
              <p className="ui text-[13px] font-semibold mb-1">Override payload (Schema.org, with replaces)</p>
              <CodeView lang="json" code={JSON.stringify({ "@context": "https://schema.org", ...node, additionalProperty: undefined, provider: undefined }, null, 2)} className="max-h-[300px]" />
            </div>
          )}
          <AddClaim entity={f} onDone={() => { g.reload(); texts.reload(); bump(); }} institution={institution} />
          <div className="ui text-[13px]">
            <p className="text-soft mb-1">Other attributes</p>
            {(ov.data?.staleness ?? []).map((s: any) => (
              <button key={s.entity_id + s.attribute} className="block underline-offset-2 hover:underline text-left"
                onClick={() => setFocus({ entityId: s.entity_id, entityName: s.entity, attribute: s.attribute })}>
                {s.entity}, {attrLabel(s.attribute).toLowerCase()}
              </button>
            ))}
          </div>
        </aside>
      </div>
    </article>
  );
}

function AddClaim({ entity, institution, onDone }: { entity: any; institution: string; onDone: () => void }) {
  const demo = useStore((s) => s.demo);
  const [text, setText] = useState("");
  const [source, setSource] = useState("retail_forum");
  const [links, setLinks] = useState(0);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setMsg(null);
    try {
      const ents = await api.entities(institution);
      const slug = ents.find((x: any) => x.id === entity.entityId)?.slug;
      const r = await api.ingestText({ institution, entity: slug, text, source_type: source, link_count: links });
      setMsg(r.claims.length ? `Filed ${r.claims.length} claim${r.claims.length > 1 ? "s" : ""}.` : "Filed the text, but it contained no figure the extractor recognised.");
      setText("");
      onDone();
    } catch (err: any) { setMsg(`Not filed: ${err.message}`); } finally { setBusy(false); }
  };
  if (demo) return <p className="ui text-[13px] text-soft border-t hairline pt-3">This demo is a read-only snapshot. Connect the live engine (set <span className="font-mono">API_URL</span>) to file new claims into the graph.</p>;
  return (
    <form onSubmit={submit} className="border-t hairline pt-3">
      <p className="ui text-[13px] font-semibold mb-1">File a new claim</p>
      <p className="text-[13.5px] text-soft mb-2">Paste a forum post, article or official notice. Numbers are extracted and weighted like the rest of the record.</p>
      <textarea className="field h-24" required value={text} onChange={(e) => setText(e.target.value)}
        placeholder={`e.g. The ${entity.entityName} ${attrLabel(entity.attribute).toLowerCase()} is 4.80% per annum w.e.f. today.`} />
      <div className="flex gap-2 mt-2">
        <select className="field" value={source} onChange={(e) => setSource(e.target.value)} aria-label="Source type">
          <option value="retail_forum">Forum post</option>
          <option value="press">Press article</option>
          <option value="institutional_web">Official web page</option>
          <option value="institutional_filing">Regulatory filing</option>
        </select>
        <input className="field w-24" type="number" min={0} value={links} onChange={(e) => setLinks(+e.target.value)} aria-label="Inbound links" />
      </div>
      <button className="btn btn-solid mt-2" disabled={busy}>{busy ? "Filing…" : "File claim"}</button>
      {msg && <p className="ui text-[13px] mt-2">{msg}</p>}
    </form>
  );
}
