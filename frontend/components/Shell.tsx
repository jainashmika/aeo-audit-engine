"use client";
import { useEffect } from "react";
import { ReflexContainer, ReflexElement, ReflexSplitter } from "react-reflex";
import { SECTIONS, useStore, type Theme } from "@/lib/store";
import { api } from "@/lib/api";
import IndexPane from "./IndexPane";
import Masthead from "./Masthead";
import Ticker from "./Ticker";
import Wire from "./Wire";
import FrontPage from "./sections/FrontPage";
import StaleFacts from "./sections/StaleFacts";
import HiddenData from "./sections/HiddenData";
import LandingGaps from "./sections/LandingGaps";
import BrandBleed from "./sections/BrandBleed";
import MachineHub from "./sections/MachineHub";
import Proof from "./sections/Proof";

const VIEWS = { front: FrontPage, stale: StaleFacts, hidden: HiddenData, landing: LandingGaps, bleed: BrandBleed, hub: MachineHub, proof: Proof };

export default function Shell() {
  const { section, go, setTheme, theme, setDemo } = useStore();
  useEffect(() => { api.health().then((h) => setDemo(!!h?.demo)).catch(() => {}); }, [setDemo]);
  useEffect(() => {
    try { const t = localStorage.getItem("aeo-theme") as Theme | null; if (t) setTheme(t); } catch {}
  }, [setTheme]);
  const View = VIEWS[section];
  const dark = theme === "darcula";

  return (
    <div className="h-screen flex flex-col">
      <Ticker />
      <Masthead />
      <ReflexContainer orientation="horizontal" className="flex-1 min-h-0">
        <ReflexElement minSize={240}>
          <ReflexContainer orientation="vertical">
            <ReflexElement size={290} minSize={200} maxSize={480} className="hidden md:block">
              <IndexPane />
            </ReflexElement>
            <ReflexSplitter />
            <ReflexElement minSize={420}>
              <div className="h-full flex flex-col">
                <nav aria-label="Sections" className={`flex overflow-x-auto scroll-thin border-b hairline px-4 ${dark ? "bg-sheet" : ""}`} role="tablist">
                  {SECTIONS.map((s) => (
                    <button key={s.id} role="tab" aria-selected={section === s.id} onClick={() => go(s.id)} title={s.term}
                      className={`ui whitespace-nowrap px-3 py-2 text-[14px] -mb-px border-b-2 ${section === s.id
                        ? `border-alert text-ink font-semibold ${dark ? "bg-paper" : ""}`
                        : "border-transparent text-soft hover:text-ink"}`}>
                      {dark ? <span className="font-mono text-[12.5px]">{s.id}.{s.id === "proof" ? "test.ts" : "tsx"}</span> : s.label}
                    </button>
                  ))}
                </nav>
                <main className="flex-1 overflow-auto scroll-thin px-6 py-6" id="main">
                  <View />
                </main>
              </div>
            </ReflexElement>
          </ReflexContainer>
        </ReflexElement>
        <ReflexSplitter />
        <ReflexElement size={170} minSize={60} maxSize={480}>
          <Wire />
        </ReflexElement>
      </ReflexContainer>
    </div>
  );
}
