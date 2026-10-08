import { create } from "zustand";

export type Theme = "broadsheet" | "darcula";
export type Section = "front" | "stale" | "hidden" | "landing" | "bleed" | "hub" | "proof";

type Focus = { entityId: string; entityName: string; attribute: string } | null;

interface State {
  theme: Theme;
  institution: string;
  section: Section;
  focus: Focus;
  hubPath: string;
  scrapeUrl: string | null;
  refreshKey: number;
  demo: boolean;
  setDemo: (d: boolean) => void;
  setTheme: (t: Theme) => void;
  setInstitution: (s: string) => void;
  go: (s: Section) => void;
  setFocus: (f: Focus) => void;
  openHub: (p: string) => void;
  openScrape: (u: string) => void;
  bump: () => void;
}

/* Deterministic state hydration: one store, synchronous setters, no derived async state. */
export const useStore = create<State>((set) => ({
  theme: "broadsheet",
  institution: "meridian",
  section: "front",
  focus: null,
  hubPath: "institutional-data/matrix.md",
  scrapeUrl: null,
  refreshKey: 0,
  demo: false,
  setDemo: (demo) => set({ demo }),
  setTheme: (theme) => {
    if (typeof document !== "undefined") {
      document.documentElement.dataset.theme = theme === "darcula" ? "darcula" : "";
      try { localStorage.setItem("aeo-theme", theme); } catch {}
    }
    set({ theme });
  },
  setInstitution: (institution) => set({ institution, focus: null, scrapeUrl: null }),
  go: (section) => set({ section }),
  setFocus: (focus) => set({ focus, section: "stale" }),
  openHub: (hubPath) => set({ hubPath, section: "hub" }),
  openScrape: (scrapeUrl) => set({ scrapeUrl, section: "hidden" }),
  bump: () => set((s) => ({ refreshKey: s.refreshKey + 1 })),
}));

export const SECTIONS: { id: Section; label: string; term: string }[] = [
  { id: "front", label: "Front page", term: "Summary of the audit" },
  { id: "stale", label: "Stale facts", term: "Corroboration Deficit" },
  { id: "hidden", label: "Hidden data", term: "Vector sparsity" },
  { id: "landing", label: "Landing gaps", term: "Context Severance" },
  { id: "bleed", label: "Brand bleed", term: "Semantic dilution" },
  { id: "hub", label: "Machine hub", term: "Payload generators" },
  { id: "proof", label: "Edge-case proof", term: "Risk validation" },
];
