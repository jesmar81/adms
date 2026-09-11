/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"SF Pro Display"',
          '"SF Pro Text"',
          '"Segoe UI"',
          "sans-serif",
        ],
      },
      colors: {
        surface: {
          canvas: "#f5f5f7",
          sidebar: "#ffffff",
          card: "#ffffff",
          input: "#ffffff",
          hover: "#f0f0f3",
        },
        line: {
          subtle: "rgba(0, 0, 0, 0.08)",
          soft: "rgba(0, 0, 0, 0.14)",
        },
        accent: {
          DEFAULT: "#0071e3",
          hover: "#0077ed",
          soft: "rgba(0, 113, 227, 0.1)",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(0, 0, 0, 0.04), 0 8px 24px -16px rgba(0, 0, 0, 0.12)",
        pop: "0 24px 64px -16px rgba(0, 0, 0, 0.25)",
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
