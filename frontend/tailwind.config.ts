import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

const token = (name: string) => `hsl(var(--${name}) / <alpha-value>)`;

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: { center: true, padding: "1rem" },
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      colors: {
        border: token("border"),
        input: token("input"),
        ring: token("ring"),
        background: token("background"),
        foreground: token("foreground"),
        primary: { DEFAULT: token("primary"), foreground: token("primary-foreground") },
        secondary: { DEFAULT: token("secondary"), foreground: token("secondary-foreground") },
        destructive: { DEFAULT: token("destructive"), foreground: token("destructive-foreground") },
        muted: { DEFAULT: token("muted"), foreground: token("muted-foreground") },
        accent: { DEFAULT: token("accent"), foreground: token("accent-foreground") },
        popover: { DEFAULT: token("popover"), foreground: token("popover-foreground") },
        card: { DEFAULT: token("card"), foreground: token("card-foreground") },
        sidebar: { DEFAULT: token("sidebar"), foreground: token("sidebar-foreground") },
        status: {
          classified: token("status-classified"),
          unclassified: token("status-unclassified"),
          duplicate: token("status-duplicate"),
          failed: token("status-failed"),
          unsupported: token("status-unsupported"),
          processing: token("status-processing"),
          downloaded: token("status-downloaded"),
        },
        chart: {
          1: token("chart-1"),
          2: token("chart-2"),
          3: token("chart-3"),
          4: token("chart-4"),
          5: token("chart-5"),
        },
      },
      borderRadius: {
        lg: "var(--radius)",          // 8px — cards
        md: "calc(var(--radius) - 2px)", // 6px — controls
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "soft-pulse": { "0%,100%": { opacity: "1" }, "50%": { opacity: ".45" } },
      },
      animation: {
        "soft-pulse": "soft-pulse 1.6s ease-in-out infinite",
      },
      transitionDuration: { DEFAULT: "150ms" },
    },
  },
  plugins: [animate],
} satisfies Config;
