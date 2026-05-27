import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        clinical: {
          bg: "#0b1220",
          panel: "#0f172a",
          surface: "#111c33",
          border: "#1e2a44",
          subtle: "#94a3b8",
          accent: "#38bdf8",
          accentSoft: "#0ea5e9",
          ok: "#22c55e",
          warn: "#f59e0b",
          risk: "#f43f5e",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(56, 189, 248, 0.25), 0 8px 30px rgba(2, 132, 199, 0.15)",
      },
    },
  },
  plugins: [],
};

export default config;
