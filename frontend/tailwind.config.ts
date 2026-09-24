import type { Config } from "tailwindcss";
import tokens from "./lib/tokens.json";

const c = tokens.colors;

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: c.surface,
        ink: { DEFAULT: c.ink, muted: c.inkMuted },
        accent: c.accent,
        danger: c.danger,
        warning: c.warning,
        success: c.success,
      },
      boxShadow: {
        neu: `-6px -6px 12px ${c.surfaceLight}, 6px 6px 12px ${c.surfaceShadow}`,
        "neu-sm": `-3px -3px 6px ${c.surfaceLight}, 3px 3px 6px ${c.surfaceShadow}`,
        "neu-lg": `-10px -10px 20px ${c.surfaceLight}, 10px 10px 20px ${c.surfaceShadow}`,
        "neu-inset": `inset 4px 4px 8px ${c.surfaceShadow}, inset -4px -4px 8px ${c.surfaceLight}`,
        "neu-inset-sm": `inset 2px 2px 4px ${c.surfaceShadow}, inset -2px -2px 4px ${c.surfaceLight}`,
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
