import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#F5F4F0",
        paper: "#FFFFFF",
        accent: "#3B82F6",
        "accent-light": "#EFF6FF",
        muted: "#78716C",
        verified: "#10B981",
        discrepancy: "#EF4444",
      },
      borderRadius: {
        card: "16px",
      },
      fontFamily: {
        display: ["var(--font-plus-jakarta)", "system-ui", "sans-serif"],
        body: ["var(--font-plus-jakarta)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "monospace"],
      },
      boxShadow: {
        card: "0 0 0 1px rgb(0 0 0 / 0.02), 0 4px 32px -8px rgb(0 0 0 / 0.06)",
        "card-hover":
          "0 0 0 1px rgb(0 0 0 / 0.03), 0 8px 40px -8px rgb(0 0 0 / 0.09)",
        "card-float":
          "0 0 0 1px rgb(0 0 0 / 0.03), 0 20px 50px -12px rgb(0 0 0 / 0.08), 0 4px 16px -4px rgb(0 0 0 / 0.03)",
      },
    },
  },
  plugins: [],
};
export default config;
