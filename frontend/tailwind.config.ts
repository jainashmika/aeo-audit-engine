import type { Config } from "tailwindcss";

// Every colour is a CSS variable so the Broadsheet (light) and Darcula themes share one class vocabulary.
// Darcula values are the exact IntelliJ hex codes from the UI specification (see app/globals.css).
const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: v("paper"),
        sheet: v("sheet"),
        ink: v("ink"),
        soft: v("soft"),
        rule: v("rule"),
        accent: v("accent"),
        tint: v("tint"),
        alert: v("alert"),
        truth: v("truth"),
        kw: v("kw"),
        str: v("str"),
        num: v("num"),
        fn: v("fn"),
      },
      fontFamily: {
        display: ["var(--font-display)"],
        body: ["var(--font-body)"],
        ui: ["var(--font-ui)"],
        mono: ["'JetBrains Mono Variable'", "'Fira Code'", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
