/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0b0d11",
          900: "#12151c",
          800: "#181c25",
          700: "#1f2430",
          600: "#2a3140",
        },
        berry: {
          400: "#ff4d7a",
          500: "#e30b5d",
          600: "#c51a4a",
        },
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "Segoe UI", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        panel: "0 12px 40px rgba(0, 0, 0, 0.28)",
      },
    },
  },
  plugins: [],
};
