/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "BlinkMacSystemFont", '"Segoe UI"', "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
      },
      colors: {
        foreground: "hsl(var(--foreground) / <alpha-value>)",
        muted: "hsl(var(--muted) / <alpha-value>)",
        surface: {
          canvas: "hsl(var(--surface-canvas) / <alpha-value>)",
          sidebar: "hsl(var(--surface-sidebar) / <alpha-value>)",
          card: "hsl(var(--surface-card) / <alpha-value>)",
          input: "hsl(var(--surface-input) / <alpha-value>)",
          hover: "hsl(var(--surface-hover) / <alpha-value>)",
          raised: "hsl(var(--surface-raised) / <alpha-value>)",
        },
        line: {
          subtle: "hsl(var(--line-subtle) / <alpha-value>)",
          soft: "hsl(var(--line-soft) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "hsl(var(--accent) / <alpha-value>)",
          hover: "hsl(var(--accent-hover) / <alpha-value>)",
          soft: "hsl(var(--accent) / 0.14)",
          50: "hsl(var(--accent) / 0.10)",
          300: "hsl(var(--accent-hover) / 0.45)",
          500: "hsl(var(--accent) / <alpha-value>)",
          600: "hsl(var(--accent-hover) / <alpha-value>)",
          700: "hsl(var(--accent-hover) / <alpha-value>)",
          800: "hsl(var(--accent-hover) / <alpha-value>)",
          900: "hsl(var(--accent-hover) / <alpha-value>)",
        },
      },
      boxShadow: {
        card: "0 1px 1px rgba(0, 0, 0, 0.3), 0 18px 45px -26px rgba(0, 0, 0, 0.9)",
        pop: "0 28px 72px -18px rgba(0, 0, 0, 0.8)",
        glow: "0 0 0 1px rgba(59,130,246,.16), 0 18px 48px -18px rgba(37,99,235,.35)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "rise-in": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "drawer-in": {
          from: { transform: "translateX(-100%)" },
          to: { transform: "translateX(0)" },
        },
        "modal-in": {
          from: { opacity: "0", transform: "translateY(10px) scale(0.98)" },
          to: { opacity: "1", transform: "translateY(0) scale(1)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.45" },
        },
      },
      animation: {
        "fade-in": "fade-in 200ms ease-out both",
        "rise-in": "rise-in 220ms ease-out both",
        "drawer-in": "drawer-in 220ms ease-out both",
        "modal-in": "modal-in 200ms ease-out both",
        shimmer: "shimmer 1.6s ease-in-out infinite",
        "pulse-dot": "pulse-dot 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
