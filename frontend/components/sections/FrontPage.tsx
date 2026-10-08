"use client";
import { api } from "@/lib/api";
import { attrLabel, num, pct, shortUrl, val } from "@/lib/format";
import { useAsync } from "@/lib/hooks";
import { useStore } from "@/lib/store";
import { Bars, Failure, Figure, Loading } from "../Bits";

export default function FrontPage() {
  const { institution, setFocus, go } = useStore();
  const ov = useAsync(() => api.overview(institution), [institution]);
  const scr = useAsync(() => api.scrapes(institution), [institution]);
  if (ov.loading && !ov.data) return <Loading what="Setting the front page" />;
  if (ov.error || !ov.data) return <Failure error={ov.error ?? "no data"} retry={ov.reload} />;
  const d = ov.data;
  const name = d.institution.name;
  const stale = [...(d.staleness ?? [])].sort((a: any, b: any) => b.corroboration_deficit - a.corroboration_deficit);
  const lead = stale.find((s: any) => s.naive_answer !== s.ground_truth) ?? stale[0];
  const worstPage = (scr.data ?? [])[0];
  const sev = (d.severance ?? []).find((s: any) => s.hydrate) ?? (d.severance ?? [])[0];
  const dil = d.dilution;

  return (
    <article className="max-w-[1180px]">
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-8">
        {/* Lead story */}
        <section>
          {lead ? (
            <>
              <h2 className="headline text-[46px] leading-[1.02] font-[620] max-w-[20ch]">
                {lead.naive_answer !== lead.ground_truth
                  ? `${num(lead.stale_claims)} posts still quote ${val(lead.naive_answer)}. ${name} says ${val(lead.ground_truth)}.`
                  : `The public record agrees with ${name} on ${lead.entity}.`}
              </h2>
              <p className="italic text-soft text-[19px] mt-3 max-w-[60ch] leading-relaxed">
                The {attrLabel(lead.attribute).toLowerCase()} on the {lead.entity} changed; the record did not.
                Weighted the way a language model weighs text, the official figure holds {pct(lead.naive_share, 2)} of
                the evidence. After temporal re-weighting it holds {pct(lead.temporal_share, 0)}.
              </p>
              <div className="grid sm:grid-cols-2 gap-8 mt-6">
                <p className="dropcap text-[16.5px] leading-[1.7] max-w-[62ch]">
                  An answer engine asked about the {lead.entity} today would most likely repeat {val(lead.naive_answer)},
                  because that figure has been posted, linked and quoted for years. The institution&apos;s own page changed,
                  but a single updated page cannot outvote a decade of forum threads on volume alone. The engine scores
                  that gap as a Corroboration Deficit of {pct(lead.corroboration_deficit, 2)}, then down-weights every
                  claim that predates the newest filing and emits a Schema.org payload that names the old figure as replaced.
                </p>
                <div className="border-t hairline pt-3">
                  <Bars rows={[
                    { label: "Official figure, as a model weighs it", value: lead.naive_share, tone: "alert", note: pct(lead.naive_share, 2) },
                    { label: "Official figure, after temporal weighting", value: lead.temporal_share, tone: "truth", note: pct(lead.temporal_share, 1) },
                  ]} />
                  <button className="btn mt-4" onClick={() => setFocus({ entityId: lead.entity_id, entityName: lead.entity, attribute: lead.attribute })}>
                    Open the evidence for this correction
                  </button>
                </div>
              </div>
            </>
          ) : <p className="text-soft">No ground-truth facts have been ingested yet.</p>}
        </section>

        {/* Corrections column */}
        <aside className="lg:border-l hairline lg:pl-6">
          <h3 className="headline text-2xl border-b-2 border-ink pb-1 mb-3">Corrections</h3>
          {stale.length === 0 && <p className="text-soft text-sm">Nothing to correct yet.</p>}
          {stale.map((s: any) => (
            <button key={s.entity_id + s.attribute} onClick={() => setFocus({ entityId: s.entity_id, entityName: s.entity, attribute: s.attribute })}
              className="block text-left mb-4 group">
              <p className="text-[14.5px] leading-snug group-hover:underline decoration-alert/60 underline-offset-2">
                {s.naive_answer !== s.ground_truth
                  ? <>An earlier version of the web said the {s.entity} {attrLabel(s.attribute).toLowerCase()} was {val(s.naive_answer)}. It is {val(s.ground_truth)}.</>
                  : <>The {s.entity} {attrLabel(s.attribute).toLowerCase()} of {val(s.ground_truth)} is confirmed by the open web.</>}
              </p>
              <p className="ui text-[12px] text-soft mt-0.5 tabnum">deficit {pct(s.corroboration_deficit, 1)}, {num(s.stale_claims)} stale claims</p>
            </button>
          ))}
        </aside>
      </div>

      {/* Lower fold: three reports */}
      <div className="grid md:grid-cols-3 gap-0 mt-8 border-t-2 border-ink">
        <section className="pt-4 md:pr-6 md:border-r hairline">
          <h3 className="headline text-[22px] leading-tight mb-2">Crawlers miss what the calculators hide</h3>
          <Figure value={pct(d.sparsity.avg_extraction_loss, 0)} label={`average share of facts a non-rendering crawler cannot read, over ${d.sparsity.pages} pages`} tone="alert" />
          {worstPage && <p className="text-[15px] mt-3 leading-relaxed">Worst page: <span className="font-mono text-[13px]">{shortUrl(worstPage.url)}</span>, where {worstPage.static_facts} of {worstPage.rendered_facts} facts are visible without JavaScript.</p>}
          <button className="btn mt-3" onClick={() => go("hidden")}>See what crawlers read</button>
        </section>
        <section className="pt-4 md:px-6 md:border-r hairline">
          <h3 className="headline text-[22px] leading-tight mb-2">AI referrals arrive at the wrong door</h3>
          {sev ? <>
            <Figure value={sev.severance_score.toFixed(2)} label={`context severance for “${sev.query}” (hydration above 0.75)`} tone={sev.hydrate ? "alert" : "truth"} />
            <p className="text-[15px] mt-3 leading-relaxed">The closest page on the site is <span className="font-mono text-[13px]">{shortUrl(sev.best_match_url)}</span>, so the engine wrote a hydration script that surfaces it on arrival.</p>
          </> : <p className="text-soft">No referral queries simulated yet.</p>}
          <button className="btn mt-3" onClick={() => go("landing")}>Test a referral query</button>
        </section>
        <section className="pt-4 md:pl-6">
          <h3 className="headline text-[22px] leading-tight mb-2">Retail fees are leaking into the premium brand</h3>
          {dil ? <>
            <Figure value={pct(dil.attribute_bleed, 0)} label="of third-party claims about institutional products quote a retail figure" tone={dil.attribute_bleed > 0.2 ? "alert" : "truth"} />
            <p className="text-[15px] mt-3 leading-relaxed">Semantic dilution index {dil.index.toFixed(2)}: the brand&apos;s overall vector leans {dil.index > 0.5 ? "retail" : "institutional"}. Partitioned namespaces stop the transfer.</p>
          </> : <p className="text-soft">Run a partition to measure dilution.</p>}
          <button className="btn mt-3" onClick={() => go("bleed")}>Compare the namespaces</button>
        </section>
      </div>
      <p className="ui text-[12.5px] text-soft mt-6 border-t hairline pt-2 tabnum">
        Graph size: {num(d.counts.text_nodes)} text nodes and {num(d.counts.claims)} attributed claims for {name}. Figures are recomputed from the temporal knowledge graph on every visit.
      </p>
    </article>
  );
}
